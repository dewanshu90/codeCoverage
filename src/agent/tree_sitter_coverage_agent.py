from typing import Dict, List, Optional
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
        # --- Tree-sitter debug: print grammar path and check if built ---
        so_path = os.environ.get("TREE_SITTER_JAVA_SO")
        if not so_path:
            so_path = str(Path(__file__).parent.parent.parent / "tree-sitter-java" / "build" / "my-languages.so")
        # print(f"[TreeSitterCoverageAgent] Loading Java grammar from: {so_path}")
        if not os.path.exists(so_path):
            print(f"[TreeSitterCoverageAgent] ERROR: Grammar .so file not found at {so_path}. Please build with 'tree-sitter build' or 'python setup.py build' in tree-sitter-java.")
        self.JAVA_LANGUAGE = Language(so_path, "java")
        self.parser = Parser()
        self.parser.set_language(self.JAVA_LANGUAGE)

    def _read_source_file(self, file_path: str) -> str:
        """Read the source code of the Java file."""
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return f.read()
        return ""

    def _read_test_file(self, class_name: str) -> str:
        """Read the existing test file for the class. Tries direct path, then recursive search if not found."""
        test_path = os.path.join(self.repo_path, "src", "test", "java", *class_name.split("/")) + "Test.java"
        if os.path.exists(test_path):
            with open(test_path, 'r') as f:
                return f.read()
        file_name = class_name.split("/")[-1] + "Test.java"
        for root, _, files in os.walk(os.path.join(self.repo_path, "src", "test", "java")):
            if file_name in files:
                alt_path = os.path.join(root, file_name)
                with open(alt_path, 'r') as f:
                    return f.read()
        return ""

    def _extract_method_basic(self, source_code: str, method_name: str) -> str:
        """Fallback: Extract method source using simple brace counting."""
        try:
            lines = source_code.split("\n")
            method_found = False
            method_lines = []
            brace_count = 0
            for line in lines:
                if not method_found:
                    if method_name in line and ("public" in line or "private" in line or "protected" in line):
                        method_found = True
                        method_lines.append(line)
                        brace_count += line.count("{") - line.count("}")
                        continue
                if method_found:
                    method_lines.append(line)
                    brace_count += line.count("{") - line.count("}")
                    if brace_count == 0:
                        break
            return "\n".join(method_lines) if method_lines else ""
        except Exception as e:
            print(f"Error extracting method source: {str(e)}")
            return ""

    def get_method_source(self, class_name: str, method_name: str) -> str:
        """Get the source code for a specific method using Tree-sitter for robust extraction."""
        source_code = self._read_source_file(class_name)
        if not source_code:
            return ""
        try:
            method_analysis = self.analyze_method(source_code, method_name)
            start_line = method_analysis.start_line
            end_line = method_analysis.end_line
            lines = source_code.split("\n")
            return "\n".join(lines[start_line - 1:end_line])
        except Exception as e:
            print(f"Tree-sitter extraction failed: {str(e)}. Falling back to basic extraction.")
            return self._extract_method_basic(source_code, method_name)

    def analyze_method(self, file_path: str, method_name: str) -> MethodAnalysis:
        """Analyze a specific method using tree-sitter syntax parsing"""
        source_code = self._read_source_file(file_path)
        if not source_code:
            raise ValueError(f"File not found or empty: {file_path}")
        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node

        # Recursively search for the method declaration node by name
        def find_method_node(node):
            if node.type == "method_declaration":
                for child in node.children:
                    if child.type == "identifier" and child.text.decode("utf8") == method_name:
                        return node
            for child in node.children:
                result = find_method_node(child)
                if result:
                    return result
            return None

        method_node = find_method_node(root_node)

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
        query = self.JAVA_LANGUAGE.query("""
            (formal_parameter
                type: (_) @type
                name: (identifier) @name
            )
        """)
        
        captures = query.captures(method_node)
        # captures is a list of (node, capture_name) tuples, in order of appearance
        # We expect pairs: type, name, type, name, ...
        for i in range(0, len(captures), 2):
            if i+1 < len(captures):
                param_type = captures[i][0].text.decode('utf8')
                param_name = captures[i+1][0].text.decode('utf8')
                params.append(f"{param_type} {param_name}")
        return params

    def _get_return_type(self, method_node) -> str:
        """Get method return type"""
        query = self.JAVA_LANGUAGE.query("""
            (method_declaration
                type: (_) @return_type
            )
        """)
        captures = query.captures(method_node)
        for node, name in captures:
            if name == 'return_type':
                return node.text.decode('utf8')
        return "void"

    def _get_throws(self, method_node) -> List[str]:
        """Get thrown exceptions"""
        throws = []
        query = self.JAVA_LANGUAGE.query("""
            (throws
                (type_list
                    (type_identifier) @exception
                )
            )
        """)
        captures = query.captures(method_node)
        for node, name in captures:
            if name == 'exception':
                throws.append(node.text.decode('utf8'))
        return throws

    def generate_structural_test_suggestions(self, method_analysis: MethodAnalysis) -> Dict:
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
                self.generate_structural_test_suggestions(method)
                for method in methods_analysis
            ]
        }

    def _find_methods_with_uncovered_lines(self, tree, uncovered_lines: List[int]):
        """Find methods that contain uncovered lines"""
        methods = set()
        query = self.JAVA_LANGUAGE.query("""
            (method_declaration
                name: (identifier) @method_name
            ) @method
        """)
        captures = query.captures(tree.root_node)
        # Each method will have two captures: method_name and method, in that order
        for i in range(0, len(captures), 2):
            if i+1 < len(captures):
                method_name_node, method_name_cap = captures[i]
                method_node, method_cap = captures[i+1]
                if method_cap == 'method' and method_name_cap == 'method_name':
                    method_name = method_name_node.text.decode('utf8')
                    start_line = method_node.start_point[0] + 1
                    end_line = method_node.end_point[0] + 1
                    if any(start_line <= line <= end_line for line in uncovered_lines):
                        methods.add(method_name)
        return methods