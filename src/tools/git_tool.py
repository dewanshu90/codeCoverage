import os
import shutil
import tempfile
from typing import Dict
import git

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

    git.Repo.clone_from(auth_url, target_dir)
    return {'project_dir': target_dir}