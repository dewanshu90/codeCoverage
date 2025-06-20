import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class MethodCoverage:
    name: str
    line: int
    instructions_missed: int
    instructions_covered: int
    branches_missed: Optional[int]
    branches_covered: Optional[int]
    lines_missed: int
    lines_covered: int
    complexity_missed: int
    complexity_covered: int

@dataclass
class ClassCoverage:
    name: str
    source_file: str
    methods: List[MethodCoverage]
    total_instructions_missed: int
    total_instructions_covered: int
    total_branches_missed: Optional[int]
    total_branches_covered: Optional[int]
    total_lines_missed: int
    total_lines_covered: int
    uncovered_lines: List[int]

class JacocoXMLAnalyzer:
    def __init__(self, xml_path: str):
        self.xml_path = xml_path
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()

    def get_counter_values(self, element, counter_type: str) -> Dict[str, int]:
        counter = element.find(f".//counter[@type='{counter_type}']")
        if counter is None:
            return {"missed": 0, "covered": 0}
        return {
            "missed": int(counter.get("missed", 0)),
            "covered": int(counter.get("covered", 0))
        }

    def get_uncovered_lines(self, sourcefile_element) -> List[int]:
        uncovered_lines = []
        for line in sourcefile_element.findall("line"):
            line_number = int(line.get("nr", 0))
            missed_instructions = int(line.get("mi", 0))
            if missed_instructions > 0:
                uncovered_lines.append(line_number)
        return uncovered_lines

    def analyze_method(self, method_element) -> MethodCoverage:
        name = method_element.get("name", "")
        line = int(method_element.get("line", 0))
        
        instr = self.get_counter_values(method_element, "INSTRUCTION")
        branch = self.get_counter_values(method_element, "BRANCH")
        lines = self.get_counter_values(method_element, "LINE")
        complexity = self.get_counter_values(method_element, "COMPLEXITY")

        return MethodCoverage(
            name=name,
            line=line,
            instructions_missed=instr["missed"],
            instructions_covered=instr["covered"],
            branches_missed=branch["missed"],
            branches_covered=branch["covered"],
            lines_missed=lines["missed"],
            lines_covered=lines["covered"],
            complexity_missed=complexity["missed"],
            complexity_covered=complexity["covered"]
        )

    def analyze_class(self, class_element, sourcefile_element) -> ClassCoverage:
        name = class_element.get("name", "")
        source_file = class_element.get("sourcefilename", "")
        
        methods = []
        for method in class_element.findall("method"):
            methods.append(self.analyze_method(method))

        instr = self.get_counter_values(class_element, "INSTRUCTION")
        branch = self.get_counter_values(class_element, "BRANCH")
        lines = self.get_counter_values(class_element, "LINE")
        
        uncovered_lines = self.get_uncovered_lines(sourcefile_element)

        return ClassCoverage(
            name=name,
            source_file=source_file,
            methods=methods,
            total_instructions_missed=instr["missed"],
            total_instructions_covered=instr["covered"],
            total_branches_missed=branch["missed"],
            total_branches_covered=branch["covered"],
            total_lines_missed=lines["missed"],
            total_lines_covered=lines["covered"],
            uncovered_lines=uncovered_lines
        )

    def analyze_coverage(self) -> List[ClassCoverage]:
        coverage_data = []
        
        for package in self.root.findall(".//package"):
            for class_element in package.findall("class"):
                source_filename = class_element.get("sourcefilename")
                sourcefile_element = package.find(f"sourcefile[@name='{source_filename}']")
                if sourcefile_element is not None:
                    coverage_data.append(self.analyze_class(class_element, sourcefile_element))
        
        return coverage_data

    def get_coverage_summary(self) -> Dict:
        total_stats = {
            "instruction": self.get_counter_values(self.root, "INSTRUCTION"),
            "branch": self.get_counter_values(self.root, "BRANCH"),
            "line": self.get_counter_values(self.root, "LINE"),
            "complexity": self.get_counter_values(self.root, "COMPLEXITY"),
            "method": self.get_counter_values(self.root, "METHOD"),
            "class": self.get_counter_values(self.root, "CLASS")
        }
        
        return {
            metric: {
                "missed": stats["missed"],
                "covered": stats["covered"],
                "total": stats["missed"] + stats["covered"],
                "coverage": (stats["covered"] / (stats["missed"] + stats["covered"])) * 100 if stats["missed"] + stats["covered"] > 0 else 0
            }
            for metric, stats in total_stats.items()
        }
