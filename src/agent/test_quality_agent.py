import logging
from typing import Dict, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

class TestQualityAgentInput(TypedDict):
    current_test_code: str
    current_target_method: Dict

class TestQualityAgentOutput(TypedDict):
    quality_verdict: Dict

class TestQualityAgent:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.parser = JsonOutputParser()
        self.system_prompt = (
            """You are a meticulous and strict Senior Test Engineer acting as an automated code reviewer. 
            Your sole purpose is to review a newly generated JUnit test method and decide if it is worth adding to the test suite.
            You MUST provide your verdict in a JSON format with two keys: 'verdict' and 'reason'.

            **Your Review Criteria:**

            1.  **DUPLICATION:**
                -   Examine the `existing_tests`. 
                -   Does the `new_test_code` test the exact same logical path or scenario as an existing test? 
                -   REJECT if it is a semantic duplicate (e.g., another test for a null input if one already exists).

            2.  **IMPACT & RELEVANCE:**
                -   Does the test target the `uncovered_lines` it was supposed to?
                -   Does it test a non-trivial piece of logic (a branch, a loop, a complex calculation)?
                -   Is it a valuable edge case (null, empty, zero, max value)?
                -   REJECT if it is a low-value test for something trivial, like a simple getter or setter.

            3.  **CODE QUALITY:**
                -   Is the test name clear and descriptive?
                -   Does it follow the Arrange-Act-Assert pattern?
                -   Is the code clean and easy to understand?
                -   REJECT if the code is messy, confusing, or does not follow best practices.

            **OUTPUT FORMAT (JSON ONLY):**
            -   If the test is good, return: `{{"verdict": "APPROVED", "reason": "The test covers a critical branch and is well-written."}}`
            -   If the test is bad, return: `{{"verdict": "REJECTED", "reason": "This test is a duplicate of the existing 'testNullInput' method."}}`
            """
        )

    def review_test_code(self, inputs: TestQualityAgentInput) -> TestQualityAgentOutput:
        """Reviews the generated test code for quality, duplication, and impact."""
        
        new_test_code = inputs.get("current_test_code")
        target_method_info = inputs.get("current_target_method")
        
        source_code = target_method_info.get("source_code", "")
        existing_tests = target_method_info.get("existing_tests", "")
        uncovered_lines = target_method_info.get("uncovered_lines", [])

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", """Please review the following new test code.

            **Class Under Test:**
            ```java
            {source_code}
            ```

            **Existing Tests:**
            ```java
            {existing_tests}
            ```

            **Uncovered Lines This Test Should Cover:**
            `{uncovered_lines}`

            **New Test Code to Review:**
            ```java
            {new_test_code}
            ```

            Provide your verdict in the specified JSON format.
            """)
        ])
        
        chain = prompt | self.llm | self.parser
        
        try:
            review_result = chain.invoke({
                "source_code": source_code,
                "existing_tests": existing_tests,
                "uncovered_lines": uncovered_lines,
                "new_test_code": new_test_code
            })
            logging.info(f"Test quality review result: {review_result}")
            return {"quality_verdict": review_result}
        except Exception as e:
            logging.error(f"Failed to parse JSON from quality agent: {e}")
            # If parsing fails, we reject it to be safe.
            return {"quality_verdict": {"verdict": "REJECTED", "reason": "Failed to get a valid JSON review."}}
