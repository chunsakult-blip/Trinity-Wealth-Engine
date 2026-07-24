import ast
import os
from pathlib import Path

def test_no_empty_test_functions():
    project_root = Path(__file__).parent.parent
    tests_dir = project_root / "tests"
    
    empty_tests = []
    
    for root, _, files in os.walk(tests_dir):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                file_path = Path(root) / file
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                            # Check if function body is just 'pass' or '...'
                            if len(node.body) == 1:
                                stmt = node.body[0]
                                if isinstance(stmt, ast.Pass):
                                    empty_tests.append(f"{file_path.name}:{node.name} (pass)")
                                elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis:
                                    empty_tests.append(f"{file_path.name}:{node.name} (...)")
                except SyntaxError:
                    pass
    
    if empty_tests:
        raise AssertionError("Found empty test functions (pass or ...):\n" + "\n".join(empty_tests))
