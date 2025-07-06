import logging
import shutil
import os
import time
from src.tools.git_tool import clone_repo

class GitCloneAgent:
    def __init__(self):
        pass

    def run(self, state: dict) -> dict:
        """
        Expects state['repo_url'], clones it, then returns
        an updated state with 'project_dir' added.
        """
        logging.info(f"GitCloneAgent invoked with state: {state}")
        repo_path = os.path.join(os.getcwd(), "cloned_repo")
        if os.path.exists(repo_path):
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    shutil.rmtree(repo_path)
                    logging.info(f"Successfully removed existing directory: {repo_path}")
                    break
                except OSError as e:
                    logging.warning(f"Attempt {attempt + 1}/{max_attempts}: Error removing directory {repo_path}: {e}")
                    if attempt < max_attempts - 1:
                        time.sleep(1)  # Wait for 1 second before retrying
                    else:
                        logging.error(f"Failed to remove directory {repo_path} after {max_attempts} attempts.")
                        return {**state, "repo_path": None, "error_message": f"Error removing existing repository: {e}"}
        out = clone_repo({"repo_url": state["repo_url"]})
        logging.info(f"GitCloneAgent output: {out}")
        return {**state, "repo_path": out["project_dir"], "error_message": out.get("error_message")}