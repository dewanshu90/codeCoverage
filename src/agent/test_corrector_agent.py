import logging

class TestCorrectorAgent:
    def __init__(self):
        pass

    def run(self, state: dict) -> dict:
        """Node to correct test code using LLM."""
        llm = state.get("llm")
        test_code = state.get("test_code")
        error_message = state.get("error_message")
        if not (llm and test_code and error_message):
            logging.warning("Missing parameters for TestCorrectorAgent")
            return state
        prompt = f"""
The following generated JUnit test failed with this error:
{error_message}

Here is the test code:
{test_code}

Please correct the test code so that it passes, and output only the corrected Java code (no explanations).
"""
        response = llm.invoke([{"role": "user", "content": prompt}])
        logging.info(f"LLM response for correction received")
        return {**state, "corrected_test_code": response.content}
