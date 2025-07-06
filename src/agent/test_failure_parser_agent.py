import logging
from typing import Optional

class TestFailureParserAgent:
    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = repo_path

    def set_repo_path(self, repo_path: str):
        self.repo_path = repo_path

    def run(self, state: dict) -> dict:
        """Node to parse test failures from maven output."""
        mvn_output = state.get("mvn_output")
        if not mvn_output:
            logging.warning("Missing mvn_output for TestFailureParserAgent")
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
