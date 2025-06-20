from typing import Dict, List
from tree_sitter import Parser, Language
import os
import asyncio
from dataclasses import dataclass
from pathlib import Path

@dataclass
class MethodAnalysis:
    name: str
    start_line: int
    end_line: int
    branches: List[Dict]
    conditions: List[Dict]
    complexity: int
    parameters: List[str]
    return_type: str
    throws: List[str]

class TreeSitterCoverageAgent:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.parser = Parser()

    def analyze_method(self, source_code: str, method_name: str) -> MethodAnalysis:
        """Analyze a specific method using tree-sitter syntax parsing"""
        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node

        # Find the method declaration
        method_node = None
        for node in root_node.children:
            if node.type == "method_declaration":
                for child in node.children:
                    if child.type == "identifier" and child.text.decode("utf8") == method_name:
                        method_node = node
                        break
                if method_node:
                    break

        if not method_node:
            raise ValueError(f"Method {method_name} not found in source code")

        # Get method name
        name_node = next(node for node in method_node.children if node.type == "identifier")
        method_name = name_node.text.decode("utf8")

        # Get parameters
        param_list = []
        params_node = next(node for node in method_node.children if node.type == "formal_parameters")
        for param in params_node.children:
            if param.type == "formal_parameter":
                param_list.append(param.text.decode("utf8"))

        # Get return type
        return_type = "void"  # Default return type
        for node in method_node.children:
            if node.type == "type_identifier":
                return_type = node.text.decode("utf8")
                break

        # Get throws declarations
        throws_list = []
        for node in method_node.children:
            if node.type == "throws":
                for exception in node.children:
                    if exception.type == "type_identifier":
                        throws_list.append(exception.text.decode("utf8"))

        # Analyze body
        body_node = next(node for node in method_node.children if node.type == "block")
        branches = self._analyze_branches(body_node)
        conditions = self._analyze_conditions(body_node)
        complexity = self._calculate_complexity(body_node)

        return MethodAnalysis(
            name=method_name,
            start_line=method_node.start_point[0] + 1,
            end_line=method_node.end_point[0] + 1,
            branches=branches,
            conditions=conditions,
            complexity=complexity,
            parameters=param_list,
            return_type=return_type,
            throws=throws_list
        )

    def _analyze_branches(self, node) -> List[Dict]:
        """Analyze branching statements (if, switch, etc.)"""
        branches = []
        branch_types = ["if_statement", "switch_statement", "for_statement", "while_statement"]
        
        def visit(node):
            if node.type in branch_types:
                branches.append({
                    "type": node.type,
                    "start": node.start_point[0] + 1,
                    "end": node.end_point[0] + 1
                })
            for child in node.children:
                visit(child)
        
        visit(node)
        return branches

    def _analyze_conditions(self, node) -> List[Dict]:
        """Analyze conditional expressions"""
        conditions = []
        condition_types = ["binary_expression", "parenthesized_expression"]
        
        def visit(node):
            if node.type in condition_types:
                parent = node.parent
                if parent and any(child.type == "condition" for child in parent.children):
                    conditions.append({
                        "expression": node.text.decode("utf8"),
                        "line": node.start_point[0] + 1
                    })
            for child in node.children:
                visit(child)
        
        visit(node)
        return conditions

    def _calculate_complexity(self, node) -> int:
        """Calculate cyclomatic complexity"""
        complexity = 1  # Base complexity
        complexity_increasing_types = [
            "if_statement", "switch_statement", "for_statement",
            "while_statement", "catch_clause", "binary_expression"
        ]
        
        def visit(node):
            nonlocal complexity
            if node.type in complexity_increasing_types:
                complexity += 1
            for child in node.children:
                visit(child)
        
        visit(node)
        return complexity

    def _extract_parameters(self, method_node) -> List[str]:
        """Extract method parameters and their types"""
        params = []
        query = self.parser.language.query("""
            (formal_parameter
                type: (_) @type
                name: (identifier) @name
            )
        """)
        
        for match in query.matches(method_node):
            param_type = match.captures[0].node.text.decode('utf8')
            param_name = match.captures[1].node.text.decode('utf8')
            params.append(f"{param_type} {param_name}")
        return params

    def _get_return_type(self, method_node) -> str:
        """Get method return type"""
        query = self.parser.language.query("""
            (method_declaration
                type: (_) @return_type
            )
        """)
        
        matches = query.matches(method_node)
        if matches:
            return matches[0].captures[0].node.text.decode('utf8')
        return "void"

    def _get_throws(self, method_node) -> List[str]:
        """Get thrown exceptions"""
        throws = []
        query = self.parser.language.query("""
            (throws
                (type_list
                    (type_identifier) @exception
                )
            )
        """)
        
        for match in query.matches(method_node):
            throws.append(match.captures[0].node.text.decode('utf8'))
        return throws

    def suggest_test_improvements(self, method_analysis: MethodAnalysis) -> Dict:
        """Generate test improvement suggestions based on Tree-sitter analysis"""
        suggestions = {
            "structure_based_tests": [],
            "edge_cases": [],
            "complexity_analysis": {
                "cyclomatic_complexity": method_analysis.complexity,
                "recommended_test_count": max(method_analysis.complexity, len(method_analysis.branches) * 2)
            }
        }
        
        # Add tests for each branch condition
        for branch in method_analysis.branches:
            suggestions["structure_based_tests"].append({
                "scenario": f"test{branch['type'].capitalize()}Condition_Line{branch['line']}",
                "focus": "Branch coverage",
                "line": branch['line'],
                "condition": branch['condition']
            })
        
        # Add edge case tests based on conditions
        for condition in method_analysis.conditions:
            suggestions["edge_cases"].append({
                "type": condition['type'],
                "line": condition['line'],
                "variants": self._generate_condition_variants(condition['text'])
            })
        
        return suggestions

    def _generate_condition_variants(self, condition: str) -> List[str]:
        """Generate variants for testing a condition"""
        variants = []
        if "==" in condition:
            variants.extend(["equal case", "non-equal case"])
        if ">" in condition or "<" in condition:
            variants.extend(["boundary case", "extreme value"])
        if "null" in condition.lower():
            variants.append("null case")
        if "length" in condition.lower():
            variants.extend(["empty", "single element", "multiple elements"])
        return variants

    async def analyze_file(self, file_path: str, uncovered_lines: List[int]) -> Dict:
        """Analyze a Java file focusing on uncovered lines"""
        with open(file_path, 'r') as f:
            source_code = f.read()
            
        tree = self.parser.parse(bytes(source_code, "utf8"))
        
        # Find methods containing uncovered lines
        methods_analysis = []
        for method in self._find_methods_with_uncovered_lines(tree, uncovered_lines):
            analysis = self.analyze_method(source_code, method)
            if analysis:
                methods_analysis.append(analysis)
                
        return {
            "file_path": file_path,
            "methods": methods_analysis,
            "suggestions": [
                self.suggest_test_improvements(method)
                for method in methods_analysis
            ]
        }

    def _find_methods_with_uncovered_lines(self, tree, uncovered_lines: List[int]):
        """Find methods that contain uncovered lines"""
        methods = set()
        query = self.parser.language.query("""
            (method_declaration
                name: (identifier) @method_name
            ) @method
        """)
        
        for match in query.matches(tree.root_node):
            method_node = match.captures[1].node
            method_name = match.captures[0].node.text.decode('utf8')
            start_line = method_node.start_point[0] + 1
            end_line = method_node.end_point[0] + 1
            
            if any(start_line <= line <= end_line for line in uncovered_lines):
                methods.add(method_name)
                
        return methods
