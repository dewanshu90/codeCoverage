from src.tree_sitter_coverage_agent import TreeSitterCoverageAgent

def main():
    # Initialize the agent
    agent = TreeSitterCoverageAgent("test_files")
    
    # Read the test file
    with open("test_files/TestClass.java", "r") as f:
        java_code = f.read()
    
    try:
        # Analyze the testMethod
        analysis = agent.analyze_method(java_code, "testMethod")
        
        # Print the analysis results
        print("Method Analysis Results:")
        print("-----------------------")
        print(f"Method Name: {analysis.name}")
        print(f"Lines: {analysis.start_line} to {analysis.end_line}")
        print(f"Return Type: {analysis.return_type}")
        print(f"Parameters: {analysis.parameters}")
        print(f"Throws: {analysis.throws}")
        print(f"Cyclomatic Complexity: {analysis.complexity}")
        print("\nBranches:")
        for branch in analysis.branches:
            print(f"  - {branch['type']} at line {branch['start']}")
        print("\nConditions:")
        for condition in analysis.conditions:
            print(f"  - Line {condition['line']}: {condition['expression']}")
            
    except Exception as e:
        print(f"Error analyzing method: {str(e)}")

if __name__ == "__main__":
    main()
