from typing import Dict
from src.tools import git_tool

class GitAgent:
    def run(self, state: Dict) -> Dict:
        repo_path = state.get('repo_path')
        class_name = state.get('current_target_method', {}).get('class_info', {}).get('class_name')
        branch_name = f"feature/test-coverage-for-{class_name.replace('/', '-')}"

        if not all([repo_path, class_name]):
            return {"error_message": "Missing repository path or class name to create a branch."}

        try:
            git_tool.create_branch(repo_path, branch_name)
            return {"branch_name": branch_name, "error_message": None}
        except Exception as e:
            return {"error_message": f"Failed to create branch: {e}"}
