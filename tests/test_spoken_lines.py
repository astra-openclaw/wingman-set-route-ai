"""Audit fixed spoken text without scraping implementation identifiers."""
import ast
from pathlib import Path
import unittest
from support import ROOT


class SpokenLineTests(unittest.TestCase):
    def test_fixed_spoken_lines_never_name_tools_or_exceptions(self):
        files = [ROOT/"set_route_ai/main.py", *sorted((ROOT/"set_route_ai/dependencies").glob("*.py"))]
        lines = []
        trusted_errors = {"DataError","BindError","NavigationStopped"}
        main_functions = {"cancel","execute_tool","_execute_request","_navigation","_edit","calibrate","settings_snapshot"}
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            # Trusted exception constructors are the only errors spoken verbatim.
            for node in ast.walk(tree):
                if (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)
                        and isinstance(node.exc.func, ast.Name) and node.exc.func.id in trusted_errors):
                    lines.extend(c.value for c in ast.walk(node.exc)
                                 if isinstance(c, ast.Constant) and isinstance(c.value, str))
            for function in ast.walk(tree):
                if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                spoken_function = (path.name == "main.py" and function.name in main_functions
                                   or path.name == "sra_navigation.py" and function.name == "plot")
                if not spoken_function:
                    continue
                for node in ast.walk(function):
                    if isinstance(node, ast.Return):
                        value = node.value
                    elif isinstance(node, ast.Assign) and any(
                            isinstance(t, ast.Name) and t.id in {"line","outcome"}
                            for t in node.targets):
                        value = node.value
                    else:
                        continue
                    lines.extend(c.value for c in ast.walk(value) if isinstance(c, ast.Constant)
                                 and isinstance(c.value,str) and (" " in c.value or "." in c.value))
            if path.name == "main.py":
                for node in tree.body:
                    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and
                            t.id in {"CANCELLED","ROUTE_CANCELLED","CALIBRATION_CANCELLED","STOPPING","UNEXPECTED","BUSY","CALIBRATION"} for t in node.targets):
                        lines.extend(c.value for c in ast.walk(node.value)
                                     if isinstance(c,ast.Constant) and isinstance(c.value,str))
        self.assertGreater(len(lines),70)
        for line in lines:
            with self.subTest(line=line):
                self.assertNotIn("_",line)
                self.assertNotRegex(line,r"Traceback|RuntimeError|OSError|Future <|Task <")
