import unittest
from unittest.mock import MagicMock, patch
import os
from typing import Dict, List, Optional, TypedDict
import subprocess # Import subprocess

# Mocking necessary modules and classes
# We need to mock the actual classes that MasterAgent imports
# to control their behavior during the test.

# Mocking the external dependencies that agents might use
class MockGitTool:
    def clone_repo(self, inputs: Dict[str, str]) -> Dict[str, str]:
        return {"project_dir": "/mock/cloned_repo"}

class MockJacocoXMLAnalyzer:
    def __init__(self, xml_path: str):
        pass
    def analyze_coverage(self):
        # Simplified mock return for coverage analysis
        return {
            "summary": {"instruction": {"coverage": 50.0}},
            "classes_needing_coverage": [
                {
                    "class_name": "com/training/example/JacocoExample/Palindrome",
                    "source_file": "Palindrome.java",
                    "uncovered_lines": [9, 10, 12, 13, 15, 16, 18],
                    "methods_needing_coverage": [
                        {
                            "method_name": "isPalindrome",
                            "line": 6,
                            "missed_instructions": 27,
                            "missed_branches": 5,
                            "coverage_metrics": {
                                "instruction_coverage": 15.625,
                                "branch_coverage": 16.666666666666664,
                            },
                        }
                    ],
                }
            ],
        }
    def get_coverage_summary(self):
        return {"instruction": {"coverage": 50.0}}

# Mocking the agents themselves
class MockGitCloneAgent:
    def run(self, state: Dict) -> Dict:
        mock_repo_path = "C:/mock/cloned_repo"
        # Create a dummy pom.xml with jacoco plugin
        pom_content = """
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.training.example</groupId>
    <artifactId>JacocoExample</artifactId>
    <version>0.0.1-SNAPSHOT</version>
    <build>
        <plugins>
            <plugin>
                <groupId>org.jacoco</groupId>
                <artifactId>jacoco-maven-plugin</artifactId>
                <version>0.8.8</version>
                <executions>
                    <execution>
                        <goals>
                            <goal>prepare-agent</goal>
                        </goals>
                    </execution>
                    <execution>
                        <id>report</id>
                        <phase>prepare-package</phase>
                        <goals>
                            <goal>report</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>
</project>
"""
        os.makedirs(mock_repo_path, exist_ok=True)
        with open(os.path.join(mock_repo_path, "pom.xml"), "w") as f:
            f.write(pom_content)
        return {"repo_path": mock_repo_path, "error_message": None}

class MockJacocoAgent:
    def run(self, state: Dict) -> Dict:
        return {"report_path": "/mock/report.html"}

class MockCoverageAnalysisAgent:
    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = repo_path
    def set_repo_path(self, repo_path: str):
        self.repo_path = repo_path
    def analyze_coverage(self, *args, **kwargs) -> Dict:
        # Simulate increased coverage after a new test is added
        return {
            "summary": {"instruction": {"coverage": 75.0, "covered": 30, "total": 40}},
            "classes_needing_coverage": [
                {
                    "class_name": "com/training/example/JacocoExample/Palindrome",
                    "source_file": "Palindrome.java",
                    "uncovered_lines": [9, 10, 12, 13, 15, 16, 18],
                    "methods_needing_coverage": [
                        {
                            "method_name": "isPalindrome",
                            "line": 6,
                            "missed_instructions": 27,
                            "missed_branches": 5,
                            "coverage_metrics": {
                                "instruction_coverage": 15.625,
                                "branch_coverage": 16.666666666666664,
                            },
                        }
                    ],
                }
            ] # No more classes needing coverage for this test
        }

class MockTestCaseGeneratorAgent:
    def __init__(self, llm: MagicMock):
        self.llm = llm
    def generate_test_suggestions(self, inputs: Dict) -> Dict:
        # Return a predictable test code that targets uncovered lines
        return {
            "current_test_code": """    @Test
    public void whenRacecarString_thenAccept() {
        Palindrome palindromeTester = new Palindrome();
        assertTrue(palindromeTester.isPalindrome("racecar"));
    }""",
            "test_class_name": "PalindromeTest",
        }

class MockTestWriterAgent:
    def run(self, state: Dict) -> Dict:
        return {"test_file_path": "/mock/test_file.java"}

class MockMavenTestRunnerAgent:
    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = repo_path
        self.mvn_path = "/mock/mvn" # Added mock mvn_path
    def set_repo_path(self, repo_path: str):
        self.repo_path = repo_path
    def run(self, state: Dict) -> Dict:
        return {"mvn_output": "Mock Maven output", "failures": []}

class MockTestFailureParserAgent:
    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = repo_path
    def set_repo_path(self, repo_path: str):
        self.repo_path = repo_path
    def run(self, state: Dict) -> Dict:
        return {"failures": []}

class MockTestCorrectorAgent:
    def run(self, state: Dict) -> Dict:
        return {"correction_suggestions": []}

class MockTestQualityAgent:
    def __init__(self, llm: MagicMock):
        self.llm = llm
    def review_test_code(self, inputs: Dict) -> Dict:
        # Always approve for this test
        return {"quality_verdict": {"verdict": "APPROVED", "reason": "Mock approval"}}

# Import the actual MasterAgent after defining mocks
from src.master_agent import MasterAgent, GraphState

class TestGenerationFlow(unittest.TestCase):

    def setUp(self):
        # Mock the LLM
        self.mock_llm = MagicMock()
        self.mock_llm.invoke.return_value.content = "Mock LLM response for test generation"

        # Instantiate MasterAgent with mock agents
        self.master_agent = MasterAgent(
            llm=self.mock_llm,
            git_clone_agent=MockGitCloneAgent(),
            jacoco_agent=MockJacocoAgent(),
            coverage_analyzer_agent=MockCoverageAnalysisAgent(),
            test_case_generator_agent=MockTestCaseGeneratorAgent(self.mock_llm),
            test_writer_agent=MockTestWriterAgent(),
            maven_test_runner_agent=MockMavenTestRunnerAgent(),
            test_failure_parser_agent=MockTestFailureParserAgent(),
            test_corrector_agent=MockTestCorrectorAgent(),
            test_quality_agent=MockTestQualityAgent(self.mock_llm),
            git_agent=MockGitAgent(), # Added mock for GitAgent
            pull_request_agent=MockPullRequestAgent()
        )
        self.app = self.master_agent.compile_graph()

    @patch('src.tools.git_tool.create_branch')
    @patch('subprocess.run')
    @patch('src.tools.jacoco_tool.run_jacoco')
    @patch('src.utils.file_utils.read_file_content')
    @patch('src.utils.file_utils.get_java_source_path')
    @patch('src.utils.file_utils.get_java_test_path')
    def test_successful_test_generation(self, mock_get_java_test_path, mock_get_java_source_path, mock_read_file_content, mock_run_jacoco, mock_subprocess_run, mock_create_branch):
        # Configure the mock to return a successful result
        mock_subprocess_run.return_value = MagicMock(returncode=0, stdout="Mock Maven output", stderr="")
        mock_create_branch.return_value = None # Mock successful branch creation
        mock_run_jacoco.return_value = "/mock/jacoco_report.html" # Mock successful jacoco run
        mock_get_java_source_path.return_value = "/mock/source.java"
        mock_get_java_test_path.return_value = "/mock/test.java"
        mock_read_file_content.side_effect = [
            "public class Palindrome { /* mock source code */ }", # For source_code
            "public class PalindromeTest { /* mock existing tests */ }" # For existing_tests
        ]

        initial_state: GraphState = {
            "repo_url": "https://github.com/mock/repo.git",
            "repo_path": "", # Will be set by git_clone_node
            "initial_coverage": None,
            "final_coverage": None,
            "current_coverage": None,
            "test_improvement_suggestions": [],
            "current_target_method": None,
            "current_test_code": "",
            "correction_suggestions": [],
            "current_correction_index": 0,
            "test_generation_attempts": 0,
            "test_file_path": "",
            "test_class_name": "",
            "failures": [],
            "quality_verdict": None,
            "rejection_reason": None,
            "current_class_index": 0,
            "current_method_index": 0,
            "error_message": None,
            "branch_name": None, # Added for new workflow
            "pull_request_url": None # Added for new workflow
        }

        # Define the sequence of nodes to execute for test generation flow
        # We want to stop right after generate_test
        nodes_to_run = [
            "git_clone",
            "initialize_agents_with_repo_path",
            "run_full_coverage",
            "select_target_class", # Changed node name
            "create_branch", # New node
            "select_target_method", # New node
            "generate_test"
        ]

        current_state = initial_state
        for node_name in nodes_to_run:
            # Manually invoke each node and update the state
            if node_name == "git_clone":
                current_state.update(self.master_agent.git_clone_node(current_state))
            elif node_name == "initialize_agents_with_repo_path":
                current_state.update(self.master_agent.initialize_agents_with_repo_path_node(current_state))
            elif node_name == "run_full_coverage":
                current_state.update(self.master_agent.run_full_coverage_node(current_state))
            elif node_name == "select_target_class": # Changed node name
                current_state.update(self.master_agent.select_target_class_node(current_state))
            elif node_name == "create_branch": # New node
                current_state.update(self.master_agent.create_branch_node(current_state))
            elif node_name == "select_target_method": # New node
                current_state.update(self.master_agent.select_target_method_node(current_state))
            elif node_name == "generate_test":
                current_state.update(self.master_agent.generate_test_node(current_state))
            
            # Break if an error occurs
            if current_state.get("error_message"):
                self.fail(f"Workflow stopped due to error: {current_state['error_message']}")

        # Assertions
        self.assertIsNotNone(current_state["current_test_code"])
        self.assertNotEqual(current_state["current_test_code"], "")
        self.assertEqual(current_state["test_class_name"], "PalindromeTest")
        self.assertIn("@Test", current_state["current_test_code"])
        print(f"Successfully generated test code: {current_state['current_test_code']}")

# Add new mocks for GitAgent and PullRequestAgent
class MockGitAgent:
    def run(self, state: Dict) -> Dict:
        return {"branch_name": "mock-branch", "error_message": None}

class MockPullRequestAgent:
    def run(self, state: Dict) -> Dict:
        return {"pull_request_url": "http://mock-pr-url.com", "error_message": None}

if __name__ == "__main__":
    unittest.main()
