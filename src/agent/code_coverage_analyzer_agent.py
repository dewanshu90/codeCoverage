import logging

from typing import Dict, List, Optional
from langgraph.graph import MessageGraph
from src.tools.jacoco_xml_analyzer import JacocoXMLAnalyzer
import os
import datetime
from src.agent.test_case_generator_agent import TestCaseGeneratorAgent
import asyncio

class CoverageAnalysisAgent:
    """
    Analyzes JaCoCo coverage reports and suggests test improvements using AI.
    Handles caching, robust method extraction, and consistent data formatting.
    """
    def __init__(self, repo_path: Optional[str] = None):
        """
        Initialize the CoverageAnalysisAgent.
        
        Args:
            repo_path (str): The root path of the Java project (should be the directory containing src/, e.g., .../cloned_repo).
        
        Note:
            For multi-project workspaces, pass the path to the actual Java project root (not the workspace root).
        """
        self.repo_path = repo_path
        self.jacoco_xml_path = None
        self.analyzer = None
        if repo_path:
            self.set_repo_path(repo_path)
        try:
            from src.agent.tree_sitter_coverage_agent import TreeSitterCoverageAgent
            self.tree_sitter_agent = TreeSitterCoverageAgent(self.repo_path)
        except ImportError:
            self.tree_sitter_agent = None
        # Caching attributes
        self._cached_coverage_data: Optional[Dict] = None
        self._cached_coverage_summary: Optional[Dict] = None
        self._cached_test_improvements: Optional[Dict] = None

    def clear_cache(self):
        """Clears all cached coverage data."""
        self._cached_coverage_data = None
        self._cached_coverage_summary = None
        self._cached_test_improvements = None

    def set_repo_path(self, repo_path: str):
        self.repo_path = repo_path
        self.jacoco_xml_path = os.path.join(repo_path, "target", "site", "jacoco", "jacoco.xml")
        

    # --- Private helpers ---
    

    def _format_coverage(self, value: float) -> str:
        """Format a coverage value as a percentage string with one decimal place."""
        try:
            return f"{float(value):.1f}%"
        except Exception:
            return str(value)

    def _windowed_uncovered_lines(self, uncovered_lines: List[int], method_line: int, window: int = 2) -> List[int]:
        """Return uncovered lines within a window before the method's start line (default 2)."""
        return [line for line in uncovered_lines if line >= method_line - window]

    

    # --- Main public API ---
    def analyze_coverage(self, *args, **kwargs) -> Dict:
        """
        Analyze the Jacoco coverage report and return detailed information about:
        - Overall coverage metrics
        - Classes with incomplete coverage
        - Methods with incomplete coverage
        - Uncovered lines that need test cases
        """
        if args or kwargs:
            raise TypeError("analyze_coverage() takes no arguments. Please call without any parameters.")
        self.analyzer = JacocoXMLAnalyzer(self.jacoco_xml_path)
        coverage_data = self.analyzer.analyze_coverage()
        summary = self.analyzer.get_coverage_summary()
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
                            "branch_coverage": (
                                (method.branches_covered / (method.branches_covered + method.branches_missed)) * 100
                                if method.branches_covered + method.branches_missed > 0 else 100
                            )
                        }
                    }
                    class_info["methods_needing_coverage"].append(method_info)
            if class_info["methods_needing_coverage"] or class_info["uncovered_lines"]:
                classes_needing_coverage.append(class_info)
        self._cached_coverage_data = {
            "summary": summary,
            "classes_needing_coverage": classes_needing_coverage
        }
        return self._cached_coverage_data

    def get_coverage_summary(self) -> Dict:
        """Return cached or fresh coverage summary."""
        if self._cached_coverage_summary is not None:
            return self._cached_coverage_summary
        self._cached_coverage_summary = self.analyzer.get_coverage_summary()
        return self._cached_coverage_summary

    def suggest_test_improvements(self, state: Dict) -> Dict:
        """
        Analyze coverage data and prepare it for the test case generator.
        """
        analysis = self.analyze_coverage()
        suggestions = []
        for class_info in analysis["classes_needing_coverage"]:
            source_code = self._read_source_file(class_info["class_name"], class_info["source_file"])
            existing_tests = self._read_test_file(class_info["class_name"])
            class_name = class_info["class_name"].split("/")[-1]
            # --- Tree-sitter structure-based suggestions ---
            structure_suggestions = None
            if self.tree_sitter_agent and source_code and class_info["uncovered_lines"]:
                try:
                    java_file_path = os.path.join(self.repo_path, "src", "main", "java", *class_info["class_name"].split("/")) + ".java"
                    result = asyncio.run(self.tree_sitter_agent.analyze_file(java_file_path, class_info["uncovered_lines"]))
                    structure_suggestions = result.get("suggestions", [])
                except Exception as e:
                    import traceback
                    print(f"[CoverageAnalysisAgent] Tree-sitter structure analysis failed: {e}\nTraceback:\n{traceback.format_exc()}")
            for method in class_info["methods_needing_coverage"]:
                method_name = method["method_name"]
                if method_name == "<init>":
                    continue
                uncovered_lines = self._windowed_uncovered_lines(class_info["uncovered_lines"], method["line"], window=2)
                # Find structure-based suggestion for this method, if available
                method_structure_suggestion = None
                if structure_suggestions:
                    for s in structure_suggestions:
                        if hasattr(s, 'name') and s.name == method_name:
                            method_structure_suggestion = s
                        elif isinstance(s, dict) and s.get('name') == method_name:
                            method_structure_suggestion = s
                suggestion = {
                    "class_name": class_name,
                    "method_name": method_name,
                    "line_number": method["line"],
                    "uncovered_lines": uncovered_lines,
                    "coverage_needed": {
                        "instruction_coverage": float(method['coverage_metrics']['instruction_coverage']),
                        "branch_coverage": float(method['coverage_metrics']['branch_coverage'])
                    },
                    "automated_analysis": {
                        "missed_branches": method["missed_branches"] > 0,
                        "missed_instructions": method["missed_instructions"] > 0,
                    },
                    "structure_suggestions": method_structure_suggestion,
                    "source_code": source_code,
                    "existing_tests": existing_tests
                }
                suggestions.append(suggestion)

        return {"test_improvement_suggestions": suggestions}

    def get_coverage_data(self) -> Dict:
        """Get coverage data and test recommendations from the JaCoCo report."""
        coverage_data = self.analyze_coverage()
        summary = self.get_coverage_summary()
        test_improvements = self.suggest_test_improvements()
        test_recommendations = []
        for suggestion in test_improvements["test_improvement_suggestions"]:
            test_recommendations.append({
                "class_name": suggestion["class_name"],
                "method_name": suggestion["method_name"],
                "coverage": {
                    "instruction_coverage": float(suggestion["coverage_needed"]["instruction_coverage"]),
                    "branch_coverage": float(suggestion["coverage_needed"]["branch_coverage"])
                },
                "uncovered_lines": suggestion["uncovered_lines"],
                "llm_suggestion": suggestion["ai_suggestions"]["ai_suggestions"],
                "structure_suggestion": suggestion.get("structure_suggestions", None)
            })
        return {
            "overall_coverage": {
                "instruction_coverage": float(summary["instruction"]["coverage"]),
                "branch_coverage": float(summary["branch"]["coverage"]),
                "line_coverage": float(summary["line"]["coverage"]),
                "complexity_coverage": float(summary["complexity"]["coverage"]),
                "method_coverage": float(summary["method"]["coverage"])
            },
            "test_recommendations": test_recommendations
        }

    def get_uncovered_methods(self) -> List[Dict]:
        """Get a list of methods that need coverage."""
        coverage_data = self.analyze_coverage()
        uncovered_methods = []
        for class_info in coverage_data["classes_needing_coverage"]:
            class_name = class_info["class_name"].split("/")[-1]
            for method in class_info["methods_needing_coverage"]:
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

    
