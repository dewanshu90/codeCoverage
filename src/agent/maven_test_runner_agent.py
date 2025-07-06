import subprocess
import shutil
import os
import logging
from typing import Optional

class MavenTestRunnerAgent:
    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = repo_path
        self.mvn_path = shutil.which("mvn") or r"C:\Program Files\Maven\apache-maven-3.8.8-bin\bin\mvn"

    def set_repo_path(self, repo_path: str):
        self.repo_path = repo_path

    def run(self, state: dict) -> dict:
        """Node to run maven tests. Can run all tests or a single, targeted test file."""
        project_dir = self.repo_path or state.get("repo_path")
        if not project_dir:
            logging.error("Missing project_dir for MavenTestRunnerAgent")
            return {**state, "mvn_output": "Error: project_dir not specified."}

        # Determine if a specific test file should be run
        # The state should provide the name of the test class (e.g., "PalindromeTest")
        test_class_name = state.get("test_class_name")

        mvn_path = shutil.which("mvn") or r"C:\Program Files\Maven\apache-maven-3.8.8-bin\bin\mvn"
        if not os.path.exists(mvn_path):
            logging.error(f"Maven executable not found at {mvn_path}")
            return {**state, "mvn_output": "Error: mvn executable not found."}

        # Run all tests (the default behavior)
        logging.info("Running all tests with 'mvn clean install'")
        command = f'"{self.mvn_path}" clean install'

        try:
            result = subprocess.run(
                command,
                cwd=project_dir,
                capture_output=True,
                text=True,
                shell=True,
                timeout=300 # 5-minute timeout for safety
            )
            output = result.stdout + "\n" + result.stderr
            logging.info(f"MavenTestRunnerAgent finished. Output length: {len(output)}")
        except subprocess.TimeoutExpired as e:
            logging.error(f"Maven command timed out: {command}")
            output = f"Timeout Error: {e.stdout}\n{e.stderr}"
        except Exception as e:
            logging.error(f"An unexpected error occurred while running Maven: {e}")
            output = f"Unexpected Error: {str(e)}"

        return {**state, "mvn_output": output}