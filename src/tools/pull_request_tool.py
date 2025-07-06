import subprocess
import logging

class PullRequestTool:
    def create_pull_request(self, repo_path: str, title: str, body: str, branch: str) -> dict:
        """Creates a pull request using the GitHub CLI."""
        try:
            # Ensure we are in the correct repository directory
            command = [
                'gh', 'pr', 'create',
                '--title', title,
                '--body', body,
                
                '--base', 'main'  # Or the default branch of your repository
            ]
            
            import os
            env = os.environ.copy()
            if os.getenv('GH_TOKEN'):
                env['GH_TOKEN'] = os.getenv('GH_TOKEN')
            logging.info(f"GH_TOKEN present in environment: {bool(env.get('GH_TOKEN'))}")
            result = subprocess.run(
                command, 
                cwd=repo_path, 
                capture_output=True, 
                text=True, 
                check=True,
                env=env
            )
            
            logging.info(f"Successfully created pull request: {result.stdout.strip()}")
            return {"pull_request_url": result.stdout.strip(), "error_message": None}
        except FileNotFoundError:
            error_msg = "GitHub CLI ('gh') not found. Please install it to use this feature."
            logging.error(error_msg)
            return {"pull_request_url": None, "error_message": error_msg}
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to create pull request: {e.stderr}"
            logging.error(error_msg)
            return {"pull_request_url": None, "error_message": error_msg}
