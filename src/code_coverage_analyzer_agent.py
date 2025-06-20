from typing import Dict, List
from langgraph.graph import MessageGraph
from tools.jacoco_xml_analyzer import JacocoXMLAnalyzer
import os
import datetime
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

class CoverageAnalysisAgent:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.jacoco_xml_path = os.path.join(repo_path, "target", "site", "jacoco", "jacoco.xml")
        self.analyzer = JacocoXMLAnalyzer(self.jacoco_xml_path)
        
        # Initialize AI components
        self.llm = ChatOpenAI(
            model_name="gpt-4.1",
            temperature=0.0,
            streaming=True
        )
        
        # Define the system prompt for test case analysis
        self.system_prompt = """You are an expert Java testing code generator. Your task is to generate ONLY pure Java JUnit test code. No explanations, comments or text should be included.

Your output rules:
1. Start with necessary imports (junit, etc.)
2. Output ONLY pure Java code that can be directly pasted into a test class
3. Each test method must have @Test annotation
4. Do not include any comments or explanatory text
5. Do not wrap code in markdown blocks or quotes
6. Do not include the test class declaration (it already exists)
7. Follow test method naming: test[Scenario]_[ExpectedResult]
8. Focus on testing:
   - Edge cases
   - Branch conditions
   - Error paths
   - Uncovered lines"""

    def analyze_coverage(self) -> Dict:
        """
        Analyzes the Jacoco coverage report and returns detailed information about:
        - Overall coverage metrics
        - Classes with incomplete coverage
        - Methods with incomplete coverage
        - Uncovered lines that need test cases
        """
        coverage_data = self.analyzer.analyze_coverage()
        summary = self.analyzer.get_coverage_summary()
        
        # Find classes and methods that need more coverage
        classes_needing_coverage = []
        for class_coverage in coverage_data:
            class_info = {
                "class_name": class_coverage.name,
                "source_file": class_coverage.source_file,
                "uncovered_lines": class_coverage.uncovered_lines,
                "methods_needing_coverage": []
            }
            
            for method in class_coverage.methods:
                if method.instructions_missed > 0 or method.branches_missed > 0:
                    method_info = {
                        "method_name": method.name,
                        "line": method.line,
                        "missed_instructions": method.instructions_missed,
                        "missed_branches": method.branches_missed,
                        "coverage_metrics": {
                            "instruction_coverage": (method.instructions_covered / (method.instructions_covered + method.instructions_missed)) * 100,
                            "branch_coverage": (method.branches_covered / (method.branches_covered + method.branches_missed)) * 100 if method.branches_covered + method.branches_missed > 0 else 100
                        }
                    }
                    class_info["methods_needing_coverage"].append(method_info)
            
            if class_info["methods_needing_coverage"] or class_info["uncovered_lines"]:
                classes_needing_coverage.append(class_info)
        
        return {
            "summary": summary,
            "classes_needing_coverage": classes_needing_coverage
        }

    def _read_source_file(self, class_name: str, source_file: str) -> str:
        """Read the source code of the Java file"""
        source_path = os.path.join(self.repo_path, "src", "main", "java",
                                 *class_name.split("/")) + ".java"
        if os.path.exists(source_path):
            with open(source_path, 'r') as f:
                return f.read()
        return ""

    def _read_test_file(self, class_name: str) -> str:
        """Read the existing test file for the class"""
        test_path = os.path.join(self.repo_path, "src", "test", "java",
                                *class_name.split("/")) + "Test.java"
        if os.path.exists(test_path):
            with open(test_path, 'r') as f:
                return f.read()
        return ""

    def _get_ai_test_suggestions(self, class_info: Dict, source_code: str, existing_tests: str) -> Dict:
        """Use AI to analyze the code and suggest specific test improvements"""
        
        # Create a detailed prompt for the AI
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", """Here is the Java code that needs test coverage:

{source_code}

Current test file:
{existing_tests}

Uncovered lines: {uncovered_lines}

Generate only the missing JUnit test methods needed to cover these lines. Output only valid Java code.""")
        ])

        # Format the messages with our data
        messages = prompt.format_messages(
            source_code=source_code,
            existing_tests=existing_tests,
            uncovered_lines=class_info["uncovered_lines"]
        )

        # Get AI response
        response = self.llm.invoke(messages)
        
        # Parse and structure the AI suggestions
        return {
            "ai_suggestions": response.content,
            "generated_timestamp": str(datetime.datetime.now())
        }

    def suggest_test_improvements(self) -> Dict:
        """
        Analyzes coverage data and suggests specific improvements needed for test cases,
        enhanced with AI-powered suggestions
        """
        analysis = self.analyze_coverage()
        
        suggestions = []
        for class_info in analysis["classes_needing_coverage"]:
            # Get source code and existing tests
            source_code = self._read_source_file(class_info["class_name"], class_info["source_file"])
            existing_tests = self._read_test_file(class_info["class_name"])
            
            # Get AI suggestions for this class
            ai_suggestions = self._get_ai_test_suggestions(
                class_info,
                source_code,
                existing_tests
            )
            
            class_name = class_info["class_name"].split("/")[-1]  # Get simple class name
            
            for method in class_info["methods_needing_coverage"]:
                method_name = method["method_name"]
                
                # Skip constructors as they usually don't need extensive testing
                if method_name == "<init>":
                    continue
                    
                suggestion = {
                    "class_name": class_name,
                    "method_name": method_name,
                    "line_number": method["line"],
                    "uncovered_lines": [line for line in class_info["uncovered_lines"] if line >= method["line"]],
                    "coverage_needed": {
                        "instruction_coverage": f"{method['coverage_metrics']['instruction_coverage']:.1f}%",
                        "branch_coverage": f"{method['coverage_metrics']['branch_coverage']:.1f}%"
                    },
                    "automated_analysis": {
                        "missed_branches": method["missed_branches"] > 0,
                        "missed_instructions": method["missed_instructions"] > 0,
                    },
                    "ai_suggestions": ai_suggestions,
                }
                suggestions.append(suggestion)

        # Calculate actual coverage from all methods
        total_instructions_missed = sum(
            method["missed_instructions"] 
            for class_info in analysis["classes_needing_coverage"] 
            for method in class_info["methods_needing_coverage"]
        )
        total_branches_missed = sum(
            method["missed_branches"] 
            for class_info in analysis["classes_needing_coverage"] 
            for method in class_info["methods_needing_coverage"]
        )
        
        # Get total covered from the first method since it contains the complete totals        
        if analysis["classes_needing_coverage"] and analysis["classes_needing_coverage"][0]["methods_needing_coverage"]:
            first_method = analysis["classes_needing_coverage"][0]["methods_needing_coverage"][0]
            instruction_coverage = first_method["coverage_metrics"]["instruction_coverage"]
            branch_coverage = first_method["coverage_metrics"]["branch_coverage"]
        else:
            instruction_coverage = analysis["summary"]["instruction"]["coverage"]
            branch_coverage = analysis["summary"]["branch"]["coverage"]
        
        return {
            "overall_coverage": {
                "instruction_coverage": f"{instruction_coverage:.1f}%",
                "branch_coverage": f"{branch_coverage:.1f}%",
                "line_coverage": f"{analysis['summary']['line']['coverage']:.1f}%"
            },
            "test_improvement_suggestions": suggestions
        }
    
    def get_coverage_data(self) -> Dict:
        """Get coverage data and test recommendations from the JaCoCo report"""
        coverage_data = self.analyze_coverage()
        summary = self.analyzer.get_coverage_summary()
        test_improvements = self.suggest_test_improvements()
        
        return {
            "overall_coverage": {
                "instruction_coverage": float(summary["instruction"]["coverage"]),
                "branch_coverage": float(summary["branch"]["coverage"]),
                "line_coverage": float(summary["line"]["coverage"]),
                "complexity_coverage": float(summary["complexity"]["coverage"]),
                "method_coverage": float(summary["method"]["coverage"])
            },
            "test_recommendations": [
                {
                    "class_name": suggestion["class_name"],
                    "method_name": suggestion["method_name"],
                    "test_code": suggestion["ai_suggestions"]["ai_suggestions"],
                    "coverage": {
                        "instruction_coverage": float(suggestion["coverage_needed"]["instruction_coverage"].rstrip('%')),
                        "branch_coverage": float(suggestion["coverage_needed"]["branch_coverage"].rstrip('%'))
                    }
                }
                for suggestion in test_improvements["test_improvement_suggestions"]
            ]
        }

    def get_uncovered_methods(self) -> List[Dict]:
        """Get a list of methods that need coverage"""
        coverage_data = self.analyze_coverage()
        uncovered_methods = []
        
        for class_info in coverage_data["classes_needing_coverage"]:
            class_name = class_info["class_name"].split("/")[-1]  # Get simple class name
            for method in class_info["methods_needing_coverage"]:
                # Skip constructors
                if method["method_name"] == "<init>":
                    continue
                    
                uncovered_methods.append({
                    "class_name": class_name,
                    "method_name": method["method_name"],
                    "line": method["line"],
                    "coverage": {
                        "instruction_coverage": method["coverage_metrics"]["instruction_coverage"],
                        "branch_coverage": method["coverage_metrics"]["branch_coverage"]
                    }
                })
                
        return uncovered_methods

    def get_method_source(self, class_name: str, method_name: str) -> str:
        """Get the source code for a specific method"""
        source_code = self._read_source_file(class_name, None)  # None since we have the class name already
        if not source_code:
            return ""

        try:
            # Very basic method extraction - in a real implementation, you'd want to use
            # a proper Java parser like JavaParser or Tree-sitter
            lines = source_code.split("\n")
            method_found = False
            method_lines = []
            brace_count = 0

            for line in lines:
                if not method_found:
                    # Look for method declaration
                    if method_name in line and ("public" in line or "private" in line or "protected" in line):
                        method_found = True
                        method_lines.append(line)
                        brace_count += line.count("{") - line.count("}")
                        continue

                if method_found:
                    method_lines.append(line)
                    brace_count += line.count("{") - line.count("}")
                    if brace_count == 0:  # Method end found
                        break

            return "\n".join(method_lines) if method_lines else ""

        except Exception as e:
            print(f"Error extracting method source: {str(e)}")
            return ""
