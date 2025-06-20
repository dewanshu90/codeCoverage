from langgraph.prebuilt import PythonFunctionNode
from src.tools.git_tool import clone_repo

# Wrap the clone_repo function into a PythonFunctionNode
git_clone_agent = PythonFunctionNode(clone_repo)
