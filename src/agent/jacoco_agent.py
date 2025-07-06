from src.tools.jacoco_tool import run_jacoco
import logging

class JacocoAgent:
    def __init__(self):
        pass

    def run(self, state: dict) -> dict:
        """
        Expects state['project_dir'], runs JaCoCo,
        then returns updated state with 'report_path'.
        """
        logging.info(f"JacocoAgent invoked with state: {state}")
        out = run_jacoco(state["repo_path"])
        logging.info(f"JacocoAgent output: {out}")
        return {**state, "report_path": out}
    
