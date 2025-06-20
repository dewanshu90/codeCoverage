from langgraph.prebuilt import PythonFunctionNode
from src.tools.jacoco_tool import run_coverage

# Wrap the run_coverage function into a PythonFunctionNode
code_coverage_agent = PythonFunctionNode(run_coverage)