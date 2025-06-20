import os
import re
import sys
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
import logging
import subprocess
import time
import shutil

# ensure src directory is on path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# ensure current directory is on path
current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)

from src.tools.git_tool import clone_repo
from src.tools.jacoco_tool import run_jacoco
from src.code_coverage_analyzer_agent import CoverageAnalysisAgent
from src.test_orchestrator_agent import TestOrchestratorAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

def git_clone_node(state: dict) -> dict:
    """
    Expects state['repo_url'], clones it, then returns
    an updated state with 'project_dir' added.
    """
    logging.info(f"git_clone_node invoked with state: {state}")
    out = clone_repo({"repo_url": state["repo_url"]})
    logging.info(f"git_clone_node output: {out}")
    return {**state, **out}

def coverage_node(state: dict) -> dict:
    """
    Expects state['project_dir'], runs JaCoCo,
    then returns updated state with 'report_path'.
    """
    logging.info(f"coverage_node invoked with state: {state}")
    out = run_jacoco(state["project_dir"])
    logging.info(f"coverage_node output: {out}")
    return {**state, "report_path": out}

def tree_sitter_coverage_node(state: dict) -> dict:
    """
    Expects state['project_dir'], analyzes coverage using TreeSitterCoverageAgent,
    then returns updated state with analysis results.
    """
    logging.info(f"tree_sitter_coverage_node invoked with state: {state}")
    from src.tree_sitter_coverage_agent import TreeSitterCoverageAgent
    agent = TreeSitterCoverageAgent(state["project_dir"])
    # For demonstration, let's assume we analyze uncovered lines from coverage report
    uncovered_lines = state.get("uncovered_lines", [])
    # For simplicity, analyze a single file or all files as needed
    # Here, just a placeholder for file_path
    file_path = state.get("file_path")
    if not file_path:
        logging.warning("No file_path provided in state for tree_sitter_coverage_node")
        return state
    analysis_result = agent.analyze_file(file_path, uncovered_lines)
    logging.info(f"tree_sitter_coverage_node output: {analysis_result}")
    return {**state, "tree_sitter_analysis": analysis_result}

def test_orchestrator_node(state: dict) -> dict:
    """
    Expects state['project_dir'], runs TestOrchestratorAgent to get test recommendations,
    then returns updated state with test suggestions.
    """
    logging.info(f"test_orchestrator_node invoked with state: {state}")
    from src.test_orchestrator_agent import TestOrchestratorAgent
    orchestrator = TestOrchestratorAgent(state["project_dir"])
    recommendations = orchestrator.get_test_recommendations()
    logging.info(f"test_orchestrator_node output: {recommendations}")
    return {**state, **recommendations}

def write_test_to_file_node(state: dict) -> dict:
    """Node to write test code to file."""
    test_code = state.get("test_code")
    class_name = state.get("class_name")
    test_dir = state.get("test_dir")
    if not (test_code and class_name and test_dir):
        logging.warning("Missing parameters for write_test_to_file_node")
        return state
    cleanedCode = re.sub(r"```[a-zA-Z]*\n?", "", test_code)
    cleanedCode = cleanedCode.replace("```", "")
    file_path = os.path.join(test_dir, f"{class_name}Test.java")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(cleanedCode)
    logging.info(f"write_test_to_file_node wrote file: {file_path}")
    return {**state, "file_path": file_path}

def run_maven_tests_node(state: dict) -> dict:
    """Node to run maven tests."""
    project_dir = state.get("project_dir")
    if not project_dir:
        logging.warning("Missing project_dir for run_maven_tests_node")
        return state
    mvn_path = shutil.which("mvn")
    if not mvn_path:
        mvn_path = r"C:\Program Files\Maven\apache-maven-3.8.8-bin\bin\mvn"
    result = subprocess.run(
        f'"{mvn_path}" test -B',
        cwd=project_dir,
        capture_output=True,
        text=True,
        shell=True
    )
    output = result.stdout + "\n" + result.stderr
    logging.info(f"run_maven_tests_node output length: {len(output)}")
    return {**state, "mvn_output": output}

def parse_test_failures_node(state: dict) -> dict:
    """Node to parse test failures from maven output."""
    mvn_output = state.get("mvn_output")
    if not mvn_output:
        logging.warning("Missing mvn_output for parse_test_failures_node")
        return state
    failures = []
    lines = mvn_output.splitlines()
    capture = False
    test_name = None
    error_message = []
    for line in lines:
        if '<<< FAILURE!' in line or '<<< ERROR!' in line:
            capture = True
            test_name = line.split()[0]
            error_message = [line]
            logging.info(f"Capturing failure for test: {test_name}")
        elif capture:
            if line.strip() == '' or line.startswith('Results :'):
                failures.append((test_name, '\n'.join(error_message)))
                capture = False
                test_name = None
                error_message = []
            else:
                error_message.append(line)
    if capture and test_name:
        failures.append((test_name, '\n'.join(error_message)))
        logging.info(f"Captured final failure for test: {test_name}")
    return {**state, "failures": failures}

def correct_test_with_llm_node(state: dict) -> dict:
    """Node to correct test code using LLM."""
    llm = state.get("llm")
    test_code = state.get("test_code")
    error_message = state.get("error_message")
    if not (llm and test_code and error_message):
        logging.warning("Missing parameters for correct_test_with_llm_node")
        return state
    prompt = f"""
The following generated JUnit test failed with this error:
{error_message}

Here is the test code:
{test_code}

Please correct the test code so that it passes, and output only the corrected Java code (no explanations).
"""
    response = llm.invoke([{"role": "user", "content": prompt}])
    logging.info(f"LLM response for correction received")
    return {**state, "corrected_test_code": response.content}

def validate_and_fix_tests_node(state: dict) -> dict:
    """Node to validate and fix tests with retries."""
    recommendations = state.get("recommendations")
    test_dir = state.get("test_dir")
    project_dir = state.get("project_dir")
    llm = state.get("llm")
    max_retries = state.get("max_retries", 10)
    if not (recommendations and test_dir and project_dir and llm):
        logging.warning("Missing parameters for validate_and_fix_tests_node")
        return state
    for rec in recommendations:
        class_name = rec.get('class_name')
        test_code = rec.get('test_code')
        if not class_name or not test_code:
            continue
        # Write initial test code
        cleanedCode = re.sub(r"```[a-zA-Z]*\n?", "", test_code)
        cleanedCode = cleanedCode.replace("```", "")
        file_path = os.path.join(test_dir, f"{class_name}Test.java")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(cleanedCode)
        for attempt in range(max_retries):
            result = subprocess.run(
                f'"{shutil.which("mvn") or r"C:\\Program Files\\Maven\\apache-maven-3.8.8-bin\\bin\\mvn"}" test -B',
                cwd=project_dir,
                capture_output=True,
                text=True,
                shell=True
            )
            mvn_output = result.stdout + "\n" + result.stderr
            failures = []
            lines = mvn_output.splitlines()
            capture = False
            test_name = None
            error_message = []
            for line in lines:
                if '<<< FAILURE!' in line or '<<< ERROR!' in line:
                    capture = True
                    test_name = line.split()[0]
                    error_message = [line]
                elif capture:
                    if line.strip() == '' or line.startswith('Results :'):
                        failures.append((test_name, '\n'.join(error_message)))
                        capture = False
                        test_name = None
                        error_message = []
                    else:
                        error_message.append(line)
            if capture and test_name:
                failures.append((test_name, '\n'.join(error_message)))
            failed = False
            for test_name, error_message in failures:
                if class_name in test_name:
                    logging.info(f"Test {test_name} failed. Attempting to auto-correct...")
                    prompt = f"""
The following generated JUnit test failed with this error:
{error_message}

Here is the test code:
{test_code}

Please correct the test code so that it passes, and output only the corrected Java code (no explanations).
"""
                    response = llm.invoke([{"role": "user", "content": prompt}])
                    test_code = response.content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(test_code)
                    failed = True
                    time.sleep(2)
                    break
            if not failed:
                logging.info(f"Test for {class_name} passed after {attempt+1} attempt(s).")
                break
        else:
            logging.warning(f"Test for {class_name} could not be auto-corrected after {max_retries} attempts.")
    return state

if __name__ == "__main__":
    # 1) Build a StateGraph whose state is a simple dict
    builder = StateGraph(dict)

    # 2) Register our nodes
    builder.add_node("git_clone", git_clone_node)
    builder.add_node("code_cov", coverage_node)
    from src.code_coverage_analyzer_agent import CoverageAnalysisAgent

    def coverage_analysis_node(state: dict) -> dict:
        """
        Expects state['project_dir'], analyzes JaCoCo coverage report using multiple agents,
        then returns updated state with enhanced analysis and test suggestions.
        """
        logging.info(f"coverage_analysis_node invoked with state: {state}")
        
        # Initialize the orchestrator that manages all agents
        orchestrator = TestOrchestratorAgent(state["project_dir"])
        
        # Get enhanced test recommendations using all agents
        recommendations = orchestrator.get_test_recommendations()
        
        out = {
            "coverage_analysis": recommendations["overall_coverage"],
            "test_recommendations": recommendations["test_recommendations"],
            "report_path": state.get("report_path", "")
        }
        logging.info(f"coverage_analysis_node output: {out}")
        return {**state, **out}

    builder.add_node("coverage_analysis", coverage_analysis_node)
    # builder.add_node("tree_sitter_coverage", tree_sitter_coverage_node)
    builder.add_node("test_orchestrator", test_orchestrator_node)
    # builder.add_node("write_test_to_file", write_test_to_file_node)
    # builder.add_node("run_maven_tests", run_maven_tests_node)
    # builder.add_node("parse_test_failures", parse_test_failures_node)
    # builder.add_node("correct_test_with_llm", correct_test_with_llm_node)
    # builder.add_node("validate_and_fix_tests", validate_and_fix_tests_node)

    # 3) Wire them up
    builder.set_entry_point("git_clone")
    builder.add_edge("git_clone", "code_cov")
    builder.add_edge("code_cov", "coverage_analysis")
    # builder.add_edge("code_cov", "tree_sitter_coverage")
    # builder.add_edge("tree_sitter_coverage", "coverage_analysis")
    builder.add_edge("coverage_analysis", "test_orchestrator")
    # builder.add_edge("test_orchestrator", "validate_and_fix_tests")
    # Do NOT add another set of edges or a second invocation!

    # 4) Compile and invoke
    app = builder.compile()
    initial = {"repo_url": os.getenv("GIT_REPO_URL")}
    final_state = app.invoke(initial)

    print("\n✨ Enhanced Analysis Results:")
    print("✅ Coverage report generated at:", final_state.get("report_path", "N/A"))
    
    print("\n📊 Coverage Analysis Summary:")
    overall = final_state.get("coverage_analysis", {})
    print(f"- Coverage Metrics:")
    print(f"  - Instruction Coverage: {overall.get('instruction_coverage', 0.0):.1f}%")
    print(f"  - Branch Coverage: {overall.get('branch_coverage', 0.0):.1f}%")
    print(f"  - Line Coverage: {overall.get('line_coverage', 0.0):.1f}%")
    print(f"  - Complexity Coverage: {overall.get('complexity_coverage', 0.0):.1f}%")
    print(f"  - Method Coverage: {overall.get('method_coverage', 0.0):.1f}%")
    
    print("\n🔍 Enhanced Test Recommendations:")
    recommendations = final_state.get("test_recommendations", [])
    if (
        overall.get("instruction_coverage", 0.0) == 100.0 and
        overall.get("branch_coverage", 0.0) == 100.0 and
        overall.get("line_coverage", 0.0) == 100.0 and
        overall.get("complexity_coverage", 0.0) == 100.0 and
        overall.get("method_coverage", 0.0) == 100.0
    ):
        print("No need to generate more test cases as coverage is already 100%.")
    else:
        for rec in recommendations:
            print(f"\n� Class: {rec.get('class_name', 'N/A')}")
            print(f"  Method: {rec.get('method_name', 'N/A')}")
            print(f"  Coverage: {rec.get('coverage', 'N/A')}")
            print(f"  Test Code:\n{rec.get('test_code', 'N/A')}")
            for key in rec:
                if key not in ['class_name', 'method_name', 'coverage', 'test_code']:
                    print(f"  {key}: {rec[key]}")
        # Run validation and feedback loop
        test_dir = os.path.join(final_state.get("project_dir", ""), "src", "test", "java", "com", "training", "example", "JacocoExample")
        project_dir = final_state.get("project_dir", "")
        from src.test_orchestrator_agent import TestOrchestratorAgent
        orchestrator = TestOrchestratorAgent(project_dir)
        # validate_and_fix_tests_node({
        #     "recommendations": recommendations,
        #     "test_dir": test_dir,
        #     "project_dir": project_dir,
        #     "llm": orchestrator.llm
        # })
