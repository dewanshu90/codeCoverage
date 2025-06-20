import os
import subprocess
import shutil
from typing import Dict

def run_jacoco(project_dir: str, report_dir: str = "site/jacoco") -> str:
    """
    Run JaCoCo code coverage analysis using Maven.

    Args:
        project_dir (str): Path to the project directory.
        report_dir (str): Relative path to the coverage report directory (default: "site/jacoco").

    Returns:
        str: Path to the generated coverage report.

    Raises:
        NotADirectoryError: If the project directory is invalid.
        FileNotFoundError: If Maven is not found or the report is missing.
        subprocess.CalledProcessError: If Maven execution fails.
    """
    if not os.path.isdir(project_dir):
        raise NotADirectoryError(f"The directory {project_dir} does not exist or is invalid.")

    mvn_path = shutil.which("mvn")
    if not mvn_path:
        raise FileNotFoundError("Maven executable not found. Ensure Maven is installed and added to PATH.")

    # Ensure the correct executable format for Windows
    if not mvn_path.endswith(".cmd"):
        mvn_path += ".cmd"

    try:
        subprocess.run([mvn_path, "clean", "test", "jacoco:report"], cwd=project_dir, check=True)
        report_path = os.path.join(project_dir, "target", report_dir, "index.html")
        if not os.path.exists(report_path):
            raise FileNotFoundError(f"Coverage report not found at {report_path}")
        return report_path
    except subprocess.CalledProcessError as e:
        print(f"Error running JaCoCo: {e}")
        raise
    except FileNotFoundError as e:
        print(f"Invalid project directory or Maven not found: {e}")
        raise