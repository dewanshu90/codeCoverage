import os
import sys
import logging
import shutil
import time
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.logging_config import setup_logging

load_dotenv() # Load environment variables from .env

from src.master_agent import MasterAgent
from src.agent.git_clone_agent import GitCloneAgent
from src.agent.jacoco_agent import JacocoAgent
from src.agent.code_coverage_analyzer_agent import CoverageAnalysisAgent
from src.agent.test_case_generator_agent import TestCaseGeneratorAgent
from src.agent.test_writer_agent import TestWriterAgent
from src.agent.maven_test_runner_agent import MavenTestRunnerAgent
from src.agent.test_failure_parser_agent import TestFailureParserAgent
from src.agent.test_corrector_agent import TestCorrectorAgent
from src.agent.test_quality_agent import TestQualityAgent
from src.agent.git_agent import GitAgent
from src.agent.pull_request_agent import PullRequestAgent
from langchain_openai import ChatOpenAI

# Configure logging early
setup_logging()

def handle_remove_readonly(func, path, exc_info):
    """Forcefully remove read-only files."""
    os.chmod(path, 0o777)
    func(path)

def remove_cloned_repo_directory():
    repo_path = os.path.join(os.getcwd(), "cloned_repo")
    temp_repo_path = os.path.join(os.getcwd(), "cloned_repo_temp")

    if os.path.exists(repo_path):
        logging.info(f"Attempting to remove existing directory: {repo_path}")
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                # First, try direct removal
                shutil.rmtree(repo_path, onerror=handle_remove_readonly)
                logging.info(f"Successfully removed directory: {repo_path}")
                return True
            except OSError as e:
                logging.warning(f"Attempt {attempt + 1}/{max_attempts}: Error during direct cleanup of {repo_path}: {e}")
                # If direct removal fails, try renaming and then removing the renamed directory
                try:
                    if os.path.exists(temp_repo_path):
                        shutil.rmtree(temp_repo_path, onerror=handle_remove_readonly)
                    os.rename(repo_path, temp_repo_path)
                    logging.info(f"Successfully renamed {repo_path} to {temp_repo_path}")
                    shutil.rmtree(temp_repo_path, onerror=handle_remove_readonly)
                    logging.info(f"Successfully removed temporary directory: {temp_repo_path}")
                    return True
                except OSError as e_rename:
                    logging.warning(f"Attempt {attempt + 1}/{max_attempts}: Error during rename/cleanup of {repo_path}: {e_rename}")
                
                if attempt < max_attempts - 1:
                    time.sleep(1)  # Wait for 1 second before retrying
                else:
                    logging.error(f"Failed to clean up directory {repo_path} after {max_attempts} attempts.")
                    return False
    return True

if __name__ == "__main__":
    # Attempt to remove the cloned_repo directory before starting
    if not remove_cloned_repo_directory():
        logging.error("Failed to clean up 'cloned_repo' directory. Exiting.")
        sys.exit(1)

    # 1. Create LLM instance
    llm_instance = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.0, streaming=True)

    # 2. Create instances of all other agents
    git_clone_agent_instance = GitCloneAgent()
    jacoco_agent_instance = JacocoAgent()
    # Note: CoverageAnalysisAgent, MavenTestRunnerAgent, TestFailureParserAgent
    # have repo_path set dynamically in git_clone_node, so initialize with empty string for now
    coverage_analyzer_agent_instance = CoverageAnalysisAgent() 
    test_case_generator_agent_instance = TestCaseGeneratorAgent(llm_instance)
    test_writer_agent_instance = TestWriterAgent()
    maven_test_runner_agent_instance = MavenTestRunnerAgent()
    test_failure_parser_agent_instance = TestFailureParserAgent()
    test_corrector_agent_instance = TestCorrectorAgent()
    test_quality_agent_instance = TestQualityAgent(llm_instance)
    git_agent_instance = GitAgent()
    pull_request_agent_instance = PullRequestAgent()

    # 3. Inject these instances into the MasterAgent constructor
    master_agent = MasterAgent(
        llm=llm_instance,
        git_clone_agent=git_clone_agent_instance,
        jacoco_agent=jacoco_agent_instance,
        coverage_analyzer_agent=coverage_analyzer_agent_instance,
        test_case_generator_agent=test_case_generator_agent_instance,
        test_writer_agent=test_writer_agent_instance,
        maven_test_runner_agent=maven_test_runner_agent_instance,
        test_failure_parser_agent=test_failure_parser_agent_instance,
        test_corrector_agent=test_corrector_agent_instance,
        test_quality_agent=test_quality_agent_instance,
        git_agent=git_agent_instance,
        pull_request_agent=pull_request_agent_instance
    )
    master_agent.run()