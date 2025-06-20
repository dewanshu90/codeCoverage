from typing import Dict, List
from code_coverage_analyzer_agent import CoverageAnalysisAgent
import os
import datetime
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import xml.etree.ElementTree as ET

class TestOrchestratorAgent:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.coverage_agent = CoverageAnalysisAgent(repo_path)
        self.tree_sitter_agent = None
        
        # Try to initialize Tree-sitter support
        try:
            from tree_sitter_coverage_agent import TreeSitterCoverageAgent
            self.tree_sitter_agent = TreeSitterCoverageAgent(repo_path)
        except Exception as e:
            print(f"Tree-sitter support not available: {str(e)}")
        
        # Initialize AI components for test generation
        self.llm = ChatOpenAI(
            model_name="gpt‑4o",
            temperature=0.0,
            streaming=True
        )
        
        # Define the system prompt for intelligent test synthesis
        self.system_prompt = """You are a Java test synthesis expert. Your task is to generate optimal test cases by combining:
1. Coverage analysis data
2. AST-based code structure analysis (when available)
3. Edge cases and boundary conditions

Rules for generated tests:
1. Include all necessary imports
2. Each test must have @Test annotation
3. Cover both positive and negative test cases
4. Include assertions to validate expected behavior
5. avoid adding redundant test cases
Also,
1. Output ONLY valid Java code for the test class or methods requested.
2. Do NOT use markdown, triple backticks, or any explanation.
3. Just output the Java code, nothing else. 
"""

    def analyze_code(self, java_code: str, method_name: str) -> Dict:
        """Analyze Java code using both coverage and AST analysis"""
        analysis = {
            "coverage": self.coverage_agent.analyze_coverage(java_code, method_name),
            "ast_analysis": None
        }
        
        # Add Tree-sitter analysis if available
        if self.tree_sitter_agent:
            try:
                analysis["ast_analysis"] = self.tree_sitter_agent.analyze_method(java_code, method_name)
            except Exception as e:
                print(f"Tree-sitter analysis failed: {str(e)}")
                
        return analysis
        
    def generate_test_cases(self, analysis: Dict, class_name: str, method_name: str) -> str:
        """Generate test cases based on the combined analysis"""
        template = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", """Generate JUnit tests for the following Java method:
Class: {class_name}
Method: {method_name}

Coverage Analysis:
{coverage_data}

AST Analysis:
{ast_data}

Generate comprehensive test cases that achieve high coverage and test edge cases.""")
        ])
        
        # Format the analysis data
        ast_data = "Not available"
        if analysis.get("ast_analysis"):
            ast = analysis["ast_analysis"]
            ast_data = f"""
- Method: {ast.name}
- Return Type: {ast.return_type}
- Parameters: {', '.join(ast.parameters)}
- Throws: {', '.join(ast.throws)}
- Complexity: {ast.complexity}
- Branches: {len(ast.branches)}
- Conditions: {len(ast.conditions)}"""

        messages = template.format_messages(
            class_name=class_name,
            method_name=method_name,
            coverage_data=analysis["coverage"],
            ast_data=ast_data
        )
        
        response = self.llm.invoke(messages)
        return response.content
    
    def get_test_recommendations(self) -> Dict:
        """Get test recommendations and coverage analysis"""
        # Parse the JaCoCo report to get coverage data
        report_path = os.path.join(self.repo_path, "target", "site", "jacoco", "index.html")
        
        # Default coverage data structure
        coverage_data = {
            "overall_coverage": {
                "instruction_coverage": 0.0,
                "branch_coverage": 0.0,
                "line_coverage": 0.0,
                "complexity_coverage": 0.0,
                "method_coverage": 0.0
            },
            "test_recommendations": [],
            "uncovered_methods": []
        }

        try:
            # Get coverage data from the coverage agent
            coverage_data = self.coverage_agent.get_coverage_data()

            # Get uncovered methods and generate test recommendations
            uncovered_methods = self.coverage_agent.get_uncovered_methods()
            
            # For each uncovered method, try to get enhanced analysis and generate tests
            for method in uncovered_methods:
                try:
                    java_code = self.coverage_agent.get_method_source(method["class_name"], method["method_name"])
                    if java_code:
                        analysis = self.analyze_code(java_code, method["method_name"])
                        test_code = self.generate_test_cases(analysis, method["class_name"], method["method_name"])
                        
                        coverage_data["test_recommendations"].append({
                            "class_name": method["class_name"],
                            "method_name": method["method_name"],
                            "test_code": test_code,
                            "coverage": method.get("coverage", 0.0),
                            "ast_analysis": analysis.get("ast_analysis")
                        })
                except Exception as e:
                    print(f"Error generating test for {method['class_name']}.{method['method_name']}: {str(e)}")
            
        except Exception as e:
            print(f"Error in get_test_recommendations: {str(e)}")
        
        return coverage_data
