import logging
from typing import Dict, TypedDict, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

class TestCaseGeneratorInput(TypedDict):
    current_target_method: Dict
    rejection_reason: Optional[str]

class TestCaseGeneratorOutput(TypedDict):
    current_test_code: str
    test_class_name: str

class TestCaseGeneratorAgent:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.system_prompt = (
            """You are a specialized Java test generation API. Your sole purpose is to write clean, complete, and valid JUnit 5 test methods.

            **CRITICAL RULES:**
            1.  **OUTPUT FORMAT:** You MUST output ONLY the raw Java code for the test method(s). The output will be directly written into an existing `.java` file.
            2.  **NO EXTRA TEXT:** DO NOT include ANY explanations, comments, apologies, or any text that is not valid Java code. 
            3.  **NO MARKDOWN:** DO NOT wrap the code in ```java ... ``` or any other markdown fences.
            4.  **NO CLASS DEFINITION:** DO NOT generate the `class ... { ... }` wrapper. It already exists. You must only generate the method(s) that go inside the class.
            5.  **REQUIRED ANNOTATION:** Every test method MUST start with the `@Test` annotation on the preceding line.

            **EXAMPLE OF A PERFECT OUTPUT:**

            ```
            @Test
            void testIsPalindrome_withNullInput() {
                Palindrome palindrome = new Palindrome();
                assertFalse(palindrome.isPalindrome(null));
            }

            @Test
            void testIsPalindrome_withEmptyString() {
                Palindrome palindrome = new Palindrome();
                assertTrue(palindrome.isPalindrome(""));
            }
            ```

            **BRANCH COVERAGE FOCUS:**
            Your primary goal is to achieve 100% branch coverage for the target method. This means:
            - For `if`/`else` statements, generate tests that cover both the `true` and `false` branches.
            - For `for`/`while` loops, generate tests that cover:
                - The loop not being entered (0 iterations).
                - The loop being entered exactly once (1 iteration).
                - The loop being entered multiple times (>1 iterations).
            - Consider edge cases and boundary conditions for all control flow statements.

            You will be given the source code of a Java class, its existing test file, and a list of uncovered lines. Your job is to write the new test methods required to cover these lines.
            """
        )

    def generate_test_suggestions(self, inputs: TestCaseGeneratorInput) -> TestCaseGeneratorOutput:
        """Use AI to analyze the code and suggest specific test improvements."""
        
        target_method_info = inputs.get('current_target_method')
        rejection_reason = inputs.get('rejection_reason')

        if not target_method_info:
            logging.error("TestCaseGeneratorAgent: No target method provided in the inputs.")
            return {"current_test_code": "", "test_class_name": ""}

        source_code = target_method_info.get("source_code", "")
        existing_tests = target_method_info.get("existing_tests", "")
        uncovered_lines = target_method_info.get("uncovered_lines", [])

        # Determine the test class name based on the target class name
        # Assuming the target_class_name is like 'com/training/example/Palindrome'
        # and we want 'PalindromeTest'
        class_name_parts = target_method_info['class_info']['class_name'].split('/')
        simple_class_name = class_name_parts[-1]
        test_class_name = f"{simple_class_name}Test"

        method_name = target_method_info['method_info']['method_name']
        if not method_name:
            logging.error("TestCaseGeneratorAgent: Method name is empty. Cannot generate test.")
            return {"current_test_code": "", "test_class_name": test_class_name}

        # Manually construct the prompt string
        human_prompt_content = f"""Here is the Java class that needs better test coverage:\n\n<source_code>\n{source_code}\n</source_code>\n\nHere is the existing test file for it:\n\n<existing_tests>\n{existing_tests}\n</existing_tests>\n\nThe following lines are not covered: {uncovered_lines}\n\nBased on the uncovered lines, generate the precise JUnit 5 test method(s) required to achieve full coverage for the method `{method_name}`. Remember, provide ONLY the raw Java code for the new method(s)."""

        if rejection_reason:
            human_prompt_content += f"\n\nPrevious test generation was rejected for the following reason: {rejection_reason}. Please address this in your new attempt."

        messages = [HumanMessage(content=human_prompt_content)]
        
        logging.info(f"Source Code Length: {len(source_code)}")
        logging.info(f"Existing Tests Length: {len(existing_tests)}")
        logging.info(f"Uncovered Lines: {uncovered_lines}")
        logging.info(f"Method Name: {method_name}")

        logging.info(f"Method Name for formatting: '{method_name}'")
        
        logging.info(f"""LLM Input Prompt: 
---
{messages}
---""")
        response = self.llm.invoke(messages)
        logging.info(f"""LLM Raw Output: 
---
{response.content}
---""")
        ai_content = response.content.strip()
        
        if not ai_content:
            logging.warning("LLM returned empty content for test generation. Returning placeholder.")
            ai_content = "// Error: LLM failed to generate test code. Please review the prompt or target method."
        
        logging.info(f"Generated test code for method: {target_method_info['method_info']['method_name']}")
        
        return {"current_test_code": ai_content, "test_class_name": test_class_name}