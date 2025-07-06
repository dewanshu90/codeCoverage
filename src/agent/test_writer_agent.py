import os
import re
import logging

class TestWriterAgent:
    def __init__(self):
        pass

    def _clean_llm_output(self, code: str) -> str:
        """Cleans the raw LLM output by removing markdown fences and other artifacts."""
        # Remove ```java ... ``` fences
        code = re.sub(r"^```(?:java)?\n", "", code, flags=re.MULTILINE)
        code = re.sub(r"\n```$", "", code, flags=re.MULTILINE)
        
        # Remove any potential class or import statements, as we only want the method.
        # This is a safety measure.
        lines = code.split('\n')
        method_lines = []
        in_method = False
        for line in lines:
            if line.strip().startswith("@Test"):
                in_method = True
            if in_method:
                method_lines.append(line)
        
        return '\n'.join(method_lines).strip()

    def _get_method_name(self, test_code: str) -> str:
        """Extracts the method name from the test code."""
        match = re.search(r"void\s+([a-zA-Z0-9_]+)\s*\(", test_code)
        if match:
            return match.group(1)
        return None

    def run(self, state: dict) -> dict:
        """Intelligently writes a test method to a file, either updating an existing
        method or appending a new one without deleting existing content."""
        
        test_code_raw = state.get("current_test_code")
        file_path = state.get("test_file_path")

        if not (test_code_raw and file_path):
            logging.warning("Missing `current_test_code` or `test_file_path` for TestWriterAgent.")
            return state

        # 1. Clean the LLM-generated code to get only the method block.
        test_code = self._clean_llm_output(test_code_raw)
        if not test_code:
            logging.warning("After cleaning, the test code is empty. Skipping write.")
            return state

        method_name = self._get_method_name(test_code)
        if not method_name:
            logging.error(f"Could not extract method name from code block. Skipping write.")
            return state

        logging.info(f"Preparing to write test method '{method_name}' to {file_path}")

        # 2. Read the existing file content.
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                # If the file doesn't exist, create a basic class structure.
                class_name = state.get("test_class_name", "GeneratedTest")
                package_name = "com.training.example" # This might need to be more dynamic
                content = f"package {package_name};\n\nimport org.junit.jupiter.api.Test;\nimport static org.junit.jupiter.api.Assertions.*;\n\nclass {class_name} {{\n}}\n"
        except IOError as e:
            logging.error(f"Error reading or creating file {file_path}: {e}")
            return state

        # 3. Find and replace the specific method if it exists.
        # This regex is designed to find a whole method, including its annotation and body.
        method_pattern = re.compile(
            r"(@Test.*?void\s+" + re.escape(method_name) + r"\s*\(.*?\{.*?\})", 
            re.DOTALL
        )
        
        if method_pattern.search(content):
            # If the method exists, replace it.
            logging.info(f"Method '{method_name}' found. Replacing it.")
            new_content = method_pattern.sub(test_code, content)
        else:
            # If the method does not exist, append it inside the class.
            logging.info(f"Method '{method_name}' not found. Appending it.")
            closing_brace_index = content.rfind('}')
            if closing_brace_index != -1:
                new_content = (
                    content[:closing_brace_index] 
                    + "    " + test_code.replace('\n', '\n    ') 
                    + "\n\n" 
                    + content[closing_brace_index:]
                )
            else:
                logging.error(f"Could not find closing brace in {file_path} to append method.")
                return state

        # 4. Write the updated content back to the file.
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            logging.info(f"Successfully wrote to {file_path}")
        except IOError as e:
            logging.error(f"Error writing to file {file_path}: {e}")

        return state