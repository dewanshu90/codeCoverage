import os
import shutil
import tempfile
from typing import Dict
import git
import logging

def clone_repo(inputs: Dict[str, str]) -> Dict[str, str]:
    """
    Clone a Git repository to a local directory.

    Args:
        inputs (Dict[str, str]): A dictionary containing the key 'repo_url', which specifies the URL of the Git repository to clone.

    Returns:
        Dict[str, str]: A dictionary containing the key 'project_dir', which specifies the path to the cloned repository.
    """
    repo_url = inputs.get('repo_url')
    if not repo_url:
        raise ValueError("GIT repository URL not provided")

    def handle_remove_readonly(func, path, exc_info):
        """Forcefully remove read-only files."""
        os.chmod(path, 0o777)
        func(path)

    token = os.getenv("GIT_TOKEN")
    # Inject token for HTTPS
    if token and repo_url.startswith("https://"):
        parts = repo_url.split("https://")
        auth_url = f"https://{token}@{parts[1]}"
    else:
        auth_url = repo_url

    target_dir = os.path.join(os.getcwd(), 'cloned_repo')
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir, onerror=handle_remove_readonly)

    try:
        repo = git.Repo.clone_from(auth_url, target_dir)
        return {'project_dir': target_dir}
    except git.exc.GitCommandError as e:
        logging.error(f"Git command error during cloning: {e.stderr}")
        return {'project_dir': None, 'error_message': f"Git command error: {e.stderr}"}
    except Exception as e:
        logging.error(f"Error cloning repository: {e}")
        return {'project_dir': None, 'error_message': str(e)}

def create_branch(repo_path: str, branch_name: str):
    """Creates and checks out a new branch."""
    try:
        repo = git.Repo(repo_path)
        repo.git.checkout('-b', branch_name)
        logging.info(f"Created and checked out new branch: {branch_name}")
    except Exception as e:
        logging.error(f"Failed to create branch {branch_name}: {e}")
        raise

def commit_changes(repo_path: str, message: str):
    """Commits all changes in the repository."""
    try:
        repo = git.Repo(repo_path)
        repo.git.add(A=True)
        repo.index.commit(message)
        logging.info(f"Committed changes with message: {message}")
    except Exception as e:
        logging.error(f"Failed to commit changes: {e}")
        raise



def reset_hard(repo_path: str):
    """Resets the repository to a clean state, discarding local changes."""
    try:
        repo = git.Repo(repo_path)
        repo.git.reset('--hard')
        logging.info(f"Performed a hard reset on repository: {repo_path}")
    except Exception as e:
        logging.error(f"Failed to perform hard reset on {repo_path}: {e}")
        raise

def push_branch(repo_path: str, branch_name: str):
    """Pushes the specified branch to the remote repository."""
    try:
        repo = git.Repo(repo_path)
        repo.git.push('origin', branch_name)
        logging.info(f"Pushed branch {branch_name} to remote.")
    except Exception as e:
        logging.error(f"Failed to push branch {branch_name}: {e}")
        raise

def checkout_branch(repo_path: str, branch_name: str):
    """Checks out an existing branch."""
    try:
        repo = git.Repo(repo_path)
        repo.git.checkout(branch_name)
        logging.info(f"Checked out branch: {branch_name}")
    except Exception as e:
        logging.error(f"Failed to checkout branch {branch_name}: {e}")
        raise



