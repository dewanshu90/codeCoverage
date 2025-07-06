import os
import logging
from typing import TypedDict, List, Dict, Optional
import datetime
import shutil
import subprocess
import time

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from src.agent.test_case_generator_agent import TestCaseGeneratorInput
from src.agent.test_quality_agent import TestQualityAgentInput
from src.utils.file_utils import get_java_source_path, get_java_test_path, read_file_content
from src.agent.pull_request_agent import PullRequestAgent
from src.agent.git_agent import GitAgent

# Define the state for the graph
class GraphState(TypedDict):
    repo_url: str
    repo_path: str
    initial_coverage: Optional[Dict]
    final_coverage: Optional[Dict]
    current_coverage: Optional[Dict]
    test_improvement_suggestions: List[Dict]
    current_target_method: Optional[Dict]
    current_test_code: str
    correction_suggestions: List[str]
    current_correction_index: int
    test_generation_attempts: int # New field to track attempts
    test_file_path: str
    test_class_name: str
    failures: List[tuple]
    quality_verdict: Optional[Dict] # New field for quality agent verdict
    rejection_reason: Optional[str] # New field for rejection reason
    current_class_index: int
    current_method_index: int
    error_message: Optional[str] # New field for error messages
    branch_name: str
    pull_request_url: str
    current_class_name: Optional[str] # Added to store the name of the current class

class MasterAgent:
    def __init__(self,
                 llm,
                 git_clone_agent,
                 jacoco_agent,
                 coverage_analyzer_agent,
                 test_case_generator_agent,
                 test_writer_agent,
                 maven_test_runner_agent,
                 test_failure_parser_agent,
                 test_corrector_agent,
                 test_quality_agent,
                 git_agent,
                 pull_request_agent):
        self.llm = llm
        self.git_clone_agent = git_clone_agent
        self.jacoco_agent = jacoco_agent
        self.coverage_analyzer_agent = coverage_analyzer_agent
        self.test_case_generator_agent = test_case_generator_agent
        self.test_writer_agent = test_writer_agent
        self.maven_test_runner_agent = maven_test_runner_agent
        self.test_failure_parser_agent = test_failure_parser_agent
        self.test_corrector_agent = test_corrector_agent
        self.test_quality_agent = test_quality_agent
        self.git_agent = git_agent
        self.pull_request_agent = pull_request_agent
        self.checkpointer = MemorySaver()

    ### NODE IMPLEMENTATIONS ###

    def initialize_agents_with_repo_path_node(self, state: GraphState) -> Dict:
        logging.info("--- Initializing Agents with Repository Path ---")
        repo_path = state['repo_path']
        if repo_path:
            self.coverage_analyzer_agent.set_repo_path(repo_path)
            self.maven_test_runner_agent.set_repo_path(repo_path)
            self.test_failure_parser_agent.set_repo_path(repo_path)
            return state
        else:
            logging.error("Repository path is None. Cannot initialize agents.")
            return {**state, "error_message": "Repository path is None after cloning."}

    def git_clone_node(self, state: GraphState) -> Dict:
        logging.info("--- Cloning Git Repository ---")
        repo_url = state["repo_url"].strip()
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                result = self.git_clone_agent.run({"repo_url": repo_url})
                if result.get("repo_path"):
                    return {"repo_path": result["repo_path"], "error_message": None}
                else:
                    raise Exception(result.get("error_message", "Unknown git clone error"))
            except Exception as e:
                error_msg = f"Git clone failed (Attempt {attempt + 1}/{max_attempts}): {e}"
                logging.error(error_msg)
                if attempt < max_attempts - 1:
                    time.sleep(2)  # Wait before retrying
                else:
                    return {"repo_path": None, "error_message": error_msg}

    def run_full_coverage_node(self, state: GraphState) -> Dict:
        logging.info("--- Analyzing Full Code Coverage ---")
        try:
            # Delete jacoco.exec before running tests to ensure fresh coverage data
            jacoco_exec_path = os.path.join(state['repo_path'], "target", "jacoco.exec")
            if os.path.exists(jacoco_exec_path):
                os.remove(jacoco_exec_path)
                logging.info(f"Deleted existing jacoco.exec: {jacoco_exec_path}")

            self.jacoco_agent.run(state) # Run JaCoCo to generate report

            analysis_result = self.coverage_analyzer_agent.analyze_coverage()
            
            updates = {
                'current_coverage': analysis_result['summary'],
                'test_improvement_suggestions': analysis_result['classes_needing_coverage'],
                'test_class_name': None, # Reset for next iteration
                'error_message': None
            }
            if state.get('initial_coverage') is None:
                updates['initial_coverage'] = analysis_result['summary']
            
            return updates
        except Exception as e:
            error_msg = f"Full coverage analysis failed: {e}"
            logging.error(error_msg)
            return {"error_message": error_msg, "test_improvement_suggestions": []}

    def select_target_class_node(self, state: GraphState) -> Dict:
        logging.info("--- Selecting Target Class ---")
        suggestions = state['test_improvement_suggestions']
        class_idx = state.get('current_class_index', 0)

        if class_idx < len(suggestions):
            target_class = suggestions[class_idx]
            logging.info(f"Selected target class: {target_class['class_name']}")
            return {
                'current_target_method': {"class_info": target_class},
                'current_method_index': 0,
                'test_generation_attempts': 0,
                'current_class_name': target_class['class_name'], # Store class name
                'current_class_index': class_idx + 1 # Increment class index here
            }
        else:
            logging.info("All classes processed.")
            return {'current_target_method': None, 'current_class_name': None}

    def create_branch_node(self, state: GraphState) -> Dict:
        logging.info("--- Creating New Branch ---")
        repo_path = state['repo_path']
        class_name = state['current_class_name']
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = f"feature/test-coverage-for-{class_name.replace('/', '-')}-{timestamp}"
        try:
            from src.tools import git_tool
            git_tool.create_branch(repo_path, branch_name)
            return {"branch_name": branch_name, "error_message": None}
        except Exception as e:
            error_msg = f"Failed to create branch {branch_name}: {e}"
            logging.error(error_msg)
            return {"error_message": error_msg}

    def select_target_method_node(self, state: GraphState) -> Dict:
        logging.info("--- Selecting Target Method ---")
        target_class = state['current_target_method']['class_info']
        methods = target_class['methods_needing_coverage']
        method_idx = state.get('current_method_index', 0)

        if method_idx < len(methods):
            target_method = methods[method_idx]
            repo_path = state['repo_path']
            dot_separated_class_name = target_class['class_name'].replace('/', '.')
            source_file_path = get_java_source_path(repo_path, dot_separated_class_name)
            test_file_path = get_java_test_path(repo_path, dot_separated_class_name)
            source_code = read_file_content(source_file_path)
            existing_tests = read_file_content(test_file_path)

            full_target_info = {
                "class_info": target_class,
                "method_info": target_method,
                "source_code": source_code,
                "existing_tests": existing_tests,
                "uncovered_lines": target_class['uncovered_lines']
            }
            logging.info(f"Selected target method: {target_method['method_name']}")
            return {'current_target_method': full_target_info, 'current_method_index': method_idx + 1}
        else:
            logging.info(f"All methods in {target_class['class_name']} processed.")
            return {'current_target_method': None}

    def generate_test_node(self, state: GraphState) -> Dict:
        logging.info("--- Generating Test Case ---")
        try:
            agent_input = TestCaseGeneratorInput(
                current_target_method=state['current_target_method'],
                rejection_reason=state.get('rejection_reason')
            )
            result = self.test_case_generator_agent.generate_test_suggestions(agent_input)
            
            self.log_generated_test_code(result['current_test_code'])
            
            return {
                "current_test_code": result['current_test_code'],
                "test_class_name": result['test_class_name'],
                "test_generation_attempts": state.get('test_generation_attempts', 0) + 1,
                "error_message": None
            }
        except Exception as e:
            error_msg = f"Test generation failed: {type(e).__name__}: {e}"
            logging.error(error_msg)
            return {"current_test_code": "", "test_class_name": "", "error_message": error_msg}

    def write_test_node(self, state: GraphState) -> Dict:
        logging.info("--- Writing Test to File ---")
        try:
            repo_path = state['repo_path']
            class_name_path = state['current_target_method']['class_info']['class_name']
            test_file_path = get_java_test_path(repo_path, class_name_path.replace('/', '.'))
            state['test_file_path'] = test_file_path
            self.test_writer_agent.run(state)
            return {"test_file_path": test_file_path, "error_message": None}
        except Exception as e:
            error_msg = f"Failed to write test file: {e}"
            logging.error(error_msg)
            return {"test_file_path": None, "error_message": error_msg}

    def run_single_test_node(self, state: GraphState) -> Dict:
        logging.info(f"--- Running Single Test: {state['test_class_name']} ---")
        try:
            maven_result = self.maven_test_runner_agent.run(state)
            failures_result = self.test_failure_parser_agent.run(maven_result)
            updates = {}
            updates.update(maven_result)
            updates.update(failures_result)
            updates['error_message'] = None
            return updates
        except Exception as e:
            error_msg = f"Single test run failed: {e}"
            logging.error(error_msg)
            return {"failures": [("Internal Error", error_msg)], "error_message": error_msg}

    def create_pull_request_node(self, state: GraphState) -> Dict:
        logging.info("--- Creating Pull Request ---")
        # Re-run full coverage analysis to get final coverage
        try:
            self.coverage_analyzer_agent.clear_cache() # Clear cache before re-analysis
            # Read jacoco.xml content for debugging
            jacoco_xml_path = os.path.join(state['repo_path'], "target", "site", "jacoco", "jacoco.xml")
            if os.path.exists(jacoco_xml_path):
                logging.info(f"Content of jacoco.xml before final analysis:\n{read_file_content(jacoco_xml_path)}")
            else:
                logging.warning(f"jacoco.xml not found at {jacoco_xml_path} before final analysis.")

            analysis_result = self.coverage_analyzer_agent.analyze_coverage()
            state['final_coverage'] = analysis_result['summary']
            return state
        except Exception as e:
            logging.error(f"Failed to get final coverage: {e}")
            state['final_coverage'] = {}

        return self.pull_request_agent.run(state)

    def log_generated_test_code(self, code: str):
        logging.info("--- Generated Test Case ---")
        try:
            from pygments import highlight
            from pygments.lexers import JavaLexer
            from pygments.formatters import TerminalFormatter
            formatted_code = highlight(code, JavaLexer(), TerminalFormatter())
            print(formatted_code)
        except ImportError:
            logging.info("Pygments not found. Printing raw code.")
            print(code)
        except Exception as e:
            logging.error(f"Could not format or print test code: {e}")
            print(code)

    ### ROUTER IMPLEMENTATIONS ###

    def should_continue_class_loop_router(self, state: GraphState) -> str:
        if state.get('current_target_method'):
            return "continue"
        else:
            # Set final_coverage when all classes are processed and workflow is ending
            state['final_coverage'] = state['current_coverage']
            return "end_workflow"

    def should_continue_method_loop_router(self, state: GraphState) -> str:
        if state.get('current_target_method'):
            return "continue"
        else:
            return "create_pull_request"

    def correction_router(self, state: GraphState) -> str:
        if not state.get('failures'):
            logging.info("Test passed successfully!")
            return "passed"
        else:
            logging.info("Test failed. Deciding on correction path.")
            return "failed"

    def handle_failed_test_router(self, state: GraphState) -> str:
        max_attempts = 3 # Define max attempts
        attempts = state.get('test_generation_attempts', 0)
        if attempts < max_attempts:
            logging.warning(f"Test failed. Retrying test generation. Attempt {attempts + 1}/{max_attempts}")
            return "retry_generation"
        else:
            logging.warning(f"Max test generation attempts ({max_attempts}) reached for current method. Skipping target.")
            # Reset attempts for the next method
            state['test_generation_attempts'] = 0
            return "skip_method"

    ### GRAPH COMPILATION ###

    def compile_graph(self):
        builder = StateGraph(GraphState)

        builder.add_node("git_clone", self.git_clone_node)
        builder.add_node("initialize_agents_with_repo_path", self.initialize_agents_with_repo_path_node)
        builder.add_node("run_full_coverage", self.run_full_coverage_node)
        builder.add_node("select_target_class", self.select_target_class_node)
        builder.add_node("create_branch", self.create_branch_node)
        builder.add_node("select_target_method", self.select_target_method_node)
        builder.add_node("generate_test", self.generate_test_node)
        builder.add_node("write_test", self.write_test_node)
        builder.add_node("run_single_test", self.run_single_test_node)
        builder.add_node("create_pull_request", self.create_pull_request_node)

        builder.add_edge(START, "git_clone")
        builder.add_edge("git_clone", "initialize_agents_with_repo_path")
        builder.add_edge("initialize_agents_with_repo_path", "run_full_coverage")
        builder.add_edge("run_full_coverage", "select_target_class")

        builder.add_conditional_edges(
            "select_target_class",
            self.should_continue_class_loop_router,
            {"continue": "create_branch", "end_workflow": END}
        )

        builder.add_edge("create_branch", "select_target_method")

        builder.add_conditional_edges(
            "select_target_method",
            self.should_continue_method_loop_router,
            {"continue": "generate_test", "create_pull_request": "create_pull_request"}
        )

        builder.add_edge("generate_test", "write_test")
        builder.add_edge("write_test", "run_single_test")

        builder.add_conditional_edges(
            "run_single_test",
            self.correction_router,
            {"passed": "run_full_coverage", "failed": "handle_failed_test"}
        )

        builder.add_node("handle_failed_test", self.handle_failed_test_router)
        builder.add_conditional_edges(
            "handle_failed_test",
            self.handle_failed_test_router,
            {"retry_generation": "generate_test", "skip_method": "select_target_method"}
        )

        builder.add_edge("create_pull_request", "select_target_class")

        return builder.compile(checkpointer=self.checkpointer)

    def run(self):
        app = self.compile_graph()
        initial_state = {
            "repo_url": os.getenv("GIT_REPO_URL").strip(),
            "current_class_index": 0,
            "current_method_index": 0,
            "test_generation_attempts": 0,
            "error_message": None,
        }
        for s in app.stream(initial_state, {"recursion_limit": 150, "configurable": {"thread_id": "1"}}):
            print(f"--- Step: {list(s.keys())[0]} ---")
            print(s)
            print("")

        # After the loop, get the final state of the graph
        final_graph_state = app.get_state({"configurable": {"thread_id": "1"}})

        print("--- Workflow Complete ---")
        initial_cov = final_graph_state.values.get('initial_coverage', {})
        final_cov = final_graph_state.values.get('current_coverage', {}) # Use current_coverage as final_coverage

        metrics = ['instruction', 'branch', 'line', 'complexity', 'method', 'class']

        metrics = ['instruction', 'branch', 'line', 'complexity', 'method', 'class']
        print("\n** JaCoCo Coverage Comparison **\n")
        print(f"{'Metric':<15} | {'Initial':<25} | {'Final':<25}")
        print("-" * 65)

        for metric in metrics:
            initial_metric_data = initial_cov.get(metric, {})
            final_metric_data = final_cov.get(metric, {})
            initial_cov_percent = initial_metric_data.get('coverage', 'N/A')
            final_cov_percent = final_metric_data.get('coverage', 'N/A')
            initial_cov_percent_str = f"{initial_cov_percent:.2f}%" if isinstance(initial_cov_percent, float) else initial_cov_percent
            final_cov_percent_str = f"{final_cov_percent:.2f}%" if isinstance(final_cov_percent, float) else final_cov_percent
            initial_details = f"{initial_metric_data.get('covered', 'N/A')} / {initial_metric_data.get('total', 'N/A')}"
            final_details = f"{final_metric_data.get('covered', 'N/A')} / {final_metric_data.get('total', 'N/A')}"
            print(f"{metric.capitalize():<15} | {f'{initial_cov_percent_str} ({initial_details})':<25} | {f'{final_cov_percent_str} ({final_details})':<25}")

        print("-" * 65)
