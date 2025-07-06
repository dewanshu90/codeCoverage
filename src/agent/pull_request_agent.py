import logging
from typing import Dict
from src.tools.pull_request_tool import PullRequestTool
from src.tools import git_tool

class PullRequestAgent:
    def __init__(self):
        self.pr_tool = PullRequestTool()

    def run(self, state: Dict) -> Dict:
        repo_path = state.get('repo_path')
        class_name = state.get('current_class_name') # Get class name from the new field
        branch_name = state.get('branch_name')
        title = f"feat(tests): Improve test coverage for {class_name}"
        body = f"This pull request automatically improves the test coverage for the `{class_name}` class."

        if not all([repo_path, class_name]):
            return {"pull_request_url": None, "error_message": "Missing repository path or class name to create a pull request."}

        # First, commit the changes
        try:
            git_tool.commit_changes(repo_path, f"feat(tests): Improve test coverage for {class_name}")
        except Exception as e:
            error_msg = f"Failed to commit changes: {e}"
            logging.error(error_msg)
            return {"pull_request_url": None, "error_message": error_msg}

        # Push the branch to remote
        try:
            git_tool.push_branch(repo_path, branch_name)
        except Exception as e:
            error_msg = f"Failed to push branch {branch_name}: {e}"
            logging.error(error_msg)
            return {"pull_request_url": None, "error_message": error_msg}

        # Then, create the pull request
        return self.pr_tool.create_pull_request(repo_path, title, body, branch_name)
