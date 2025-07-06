import os
from typing import Optional

def get_java_source_path(repo_path: str, class_name: str) -> str:
    """Constructs the absolute path to a Java source file."""
    parts = class_name.split('.')
    return os.path.join(repo_path, "src", "main", "java", *parts) + ".java"

def get_java_test_path(repo_path: str, class_name: str) -> str:
    """Constructs the absolute path to a Java test file."""
    parts = class_name.split('.')
    return os.path.join(repo_path, "src", "test", "java", *parts) + "Test.java"

def read_file_content(absolute_path: str) -> Optional[str]:
    """Reads and returns the content of a file, or None if not found."""
    if os.path.exists(absolute_path):
        with open(absolute_path, 'r', encoding='utf-8') as f:
            return f.read()
    return None

def write_file_content(absolute_path: str, content: str):
    """Writes content to a file, creating directories if necessary."""
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, 'w', encoding='utf-8') as f:
        f.write(content)
