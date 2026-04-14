"""
Code to Numeric Logic — MVP Converter
Python → C++ pattern-based translator with AST analysis.
"""

import ast
import json
import re
from pathlib import Path
from dataclasses import dataclass, field


PATTERNS_PATH = Path(__file__).parent / "patterns.json"


@dataclass
class ConversionResult:
    cpp_code: str
    patterns_used: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    headers_needed: set[str] = field(default_factory=set)


def load_patterns() -> list[dict]:
    with open(PATTERNS_PATH) as f:
        data = json.load(f)
    return data["patterns"]


def infer_type(node: ast.expr) -> str:
    """Infer C++ type from a Python AST expression."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "bool"
        if isinstance(node.value, int):
            return "int"
        if isinstance(node.value, float):
            return "double"
        if isinstance(node.value, str):
            return "std::string"
    if isinstance(node, ast.List):
        if node.elts:
            inner = infer_type(node.elts[0])
            return f"std::vector<{inner}>"
        return "std::vector<int>"
    if isinstance(node, ast.Dict):
        if node.keys and node.keys[0] is not None:
            kt = infer_type(node.keys[0])
            vt = infer_type(node.values[0])
            return f"std::map<{kt}, {vt}>"
        return "std::map<std::string, std::string>"
    if isinstance(node, ast.BinOp):
        left_t = infer_type(node.left)
        right_t = infer_type(node.right)
        if "double" in (left_t, right_t):
            return "double"
        if "std::string" in (left_t, right_t):
            return "std::string"
        return "int"
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id == "len":
                return "int"
            if node.func.id in ("int", "float", "str", "bool"):
                return {"int": "int", "float": "double", "str": "std::string", "bool": "bool"}[node.func.id]
        return "auto"
    if isinstance(node, ast.Compare):
        return "bool"
    if isinstance(node, ast.BoolOp):
        return "bool"
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return "bool"
    return "auto"


def infer_return_type(func_node: ast.FunctionDef) -> str:
    """Infer return type from type annotation or body analysis."""
    if func_node.returns:
        return annotation_to_cpp(func_node.returns)
    for node in ast.walk(func_node):
        if isinstance(node, ast.Return) and node.value is not None:
            return infer_type(node.value)
    return "void"


def annotation_to_cpp(node: ast.expr) -> str:
    """Convert a Python type annotation to C++ type."""
    if isinstance(node, ast.Name):
        mapping = {"int": "int", "float": "double", "str": "std::string", "bool": "bool", "None": "void"}
        return mapping.get(node.id, "auto")
    if isinstance(node, ast.Constant):
        if node.value is None:
            return "void"
        if isinstance(node.value, str):
            mapping = {"int": "int", "float": "double", "str": "std::string", "bool": "bool"}
            return mapping.get(node.value, "auto")
    return "auto"


class PythonToCppConverter:
    def __init__(self):
        self.headers: set[str] = set()
        self.patterns_used: list[str] = []
        self.warnings: list[str] = []
        self.indent_level: int = 0

    def indent(self) -> str:
        return "    " * self.indent_level

    def convert(self, python_code: str) -> ConversionResult:
        self.headers = {"<iostream>"}
        self.patterns_used = []
        self.warnings = []
        self.indent_level = 0

        try:
            tree = ast.parse(python_code)
        except SyntaxError as e:
            return ConversionResult(
                cpp_code=f"// Syntax error: {e.msg} (line {e.lineno})",
                warnings=[f"Python syntax error: {e.msg}"]
            )

        body_lines = self._convert_body(tree.body)

        has_main_guard = any(
            isinstance(n, ast.If) and self._is_main_guard(n)
            for n in tree.body
        )

        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        non_functions = [n for n in tree.body if not isinstance(n, ast.FunctionDef) and not (isinstance(n, ast.If) and self._is_main_guard(n))]

        if has_main_guard:
            cpp_lines = body_lines
        elif functions and not non_functions:
            cpp_lines = body_lines
        else:
            func_lines = []
            main_lines = []
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    func_lines.extend(self._convert_node(node))
                    func_lines.append("")
                else:
                    self.indent_level = 1
                    main_lines.extend(self._convert_node(node))
                    self.indent_level = 0

            cpp_lines = func_lines
            if main_lines:
                self.patterns_used.append("P030")
                cpp_lines.append("int main() {")
                cpp_lines.extend(main_lines)
                cpp_lines.append("    return 0;")
                cpp_lines.append("}")

        header_lines = [f"#include {h}" for h in sorted(self.headers)]
        header_lines.append("using namespace std;")
        header_lines.append("")

        all_lines = header_lines + cpp_lines
        cpp_code = "\n".join(all_lines)

        cpp_code = cpp_code.replace("std::cout", "cout")
        cpp_code = cpp_code.replace("std::endl", "endl")
        cpp_code = cpp_code.replace("std::string", "string")
        cpp_code = cpp_code.replace("std::vector", "vector")
        cpp_code = cpp_code.replace("std::map", "map")

        return ConversionResult(
            cpp_code=cpp_code,
            patterns_used=list(set(self.patterns_used)),
            warnings=self.warnings,
            headers_needed=self.headers
        )

    def _convert_body(self, stmts: list[ast.stmt]) -> list[str]:
        lines = []
        for stmt in stmts:
            lines.extend(self._convert_node(stmt))
        return lines

    def _convert_node(self, node: ast.stmt) -> list[str]:
        if isinstance(node, ast.Assign):
            return self._convert_assign(node)
        if isinstance(node, ast.AugAssign):
            return self._convert_aug_assign(node)
        if isinstance(node, ast.Expr):
            return self._convert_expr_stmt(node)
        if isinstance(node, ast.If):
            if self._is_main_guard(node):
                return self._convert_main_guard(node)
            return self._convert_if(node)
        if isinstance(node, ast.For):
            return self._convert_for(node)
        if isinstance(node, ast.While):
            return self._convert_while(node)
        if isinstance(node, ast.FunctionDef):
            return self._convert_function(node)
        if isinstance(node, ast.Return):
            return self._convert_return(node)
        if isinstance(node, ast.Break):
            self.patterns_used.append("P028")
            return [f"{self.indent()}break;"]
        if isinstance(node, ast.Continue):
            self.patterns_used.append("P029")
            return [f"{self.indent()}continue;"]
        if isinstance(node, ast.Pass):
            return [f"{self.indent()}// pass"]

        self.warnings.append(f"Unsupported: {type(node).__name__} at line {getattr(node, 'lineno', '?')}")
        return [f"{self.indent()}// TODO: unsupported {type(node).__name__}"]

    def _convert_assign(self, node: ast.Assign) -> list[str]:
        if len(node.targets) != 1:
            self.warnings.append("Multiple assignment targets not supported")
            return [f"{self.indent()}// TODO: multiple assignment"]

        target = node.targets[0]
        if not isinstance(target, ast.Name):
            self.warnings.append(f"Complex assignment target: {type(target).__name__}")
            return [f"{self.indent()}// TODO: complex target"]

        name = target.id
        cpp_type = infer_type(node.value)
        value_str = self._expr_to_cpp(node.value)

        if "vector" in cpp_type:
            self.headers.add("<vector>")
            self.patterns_used.append("P005")
        if "map" in cpp_type:
            self.headers.add("<map>")
            self.patterns_used.append("P024")
        if "string" in cpp_type:
            self.headers.add("<string>")
            self.patterns_used.append("P003")
        if cpp_type == "int":
            self.patterns_used.append("P001")
        if cpp_type == "double":
            self.patterns_used.append("P002")
        if cpp_type == "bool":
            self.patterns_used.append("P004")

        return [f"{self.indent()}{cpp_type} {name} = {value_str};"]

    def _convert_aug_assign(self, node: ast.AugAssign) -> list[str]:
        target = self._expr_to_cpp(node.target)
        value = self._expr_to_cpp(node.value)
        op_map = {
            ast.Add: "+=", ast.Sub: "-=", ast.Mult: "*=",
            ast.Div: "/=", ast.Mod: "%=",
        }
        op = op_map.get(type(node.op), "+=")
        return [f"{self.indent()}{target} {op} {value};"]

    def _convert_expr_stmt(self, node: ast.Expr) -> list[str]:
        if isinstance(node.value, ast.Call):
            return self._convert_call_stmt(node.value)
        return [f"{self.indent()}{self._expr_to_cpp(node.value)};"]

    def _convert_call_stmt(self, node: ast.Call) -> list[str]:
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            return self._convert_print(node)
        if isinstance(node.func, ast.Attribute):
            obj = self._expr_to_cpp(node.func.value)
            method = node.func.attr
            if method == "append":
                self.patterns_used.append("P022")
                arg = self._expr_to_cpp(node.args[0]) if node.args else ""
                return [f"{self.indent()}{obj}.push_back({arg});"]
        return [f"{self.indent()}{self._expr_to_cpp(node)};"]

    def _convert_print(self, node: ast.Call) -> list[str]:
        self.headers.add("<iostream>")
        if not node.args:
            self.patterns_used.append("P006")
            return [f"{self.indent()}cout << endl;"]
        if len(node.args) == 1:
            arg = node.args[0]
            if isinstance(arg, ast.JoinedStr):
                self.patterns_used.append("P009")
                parts = self._fstring_to_cout(arg)
                return [f"{self.indent()}cout << {parts} << endl;"]
            self.patterns_used.append("P006")
            return [f"{self.indent()}cout << {self._expr_to_cpp(arg)} << endl;"]

        self.patterns_used.append("P008")
        parts = ' << " " << '.join(self._expr_to_cpp(a) for a in node.args)
        return [f"{self.indent()}cout << {parts} << endl;"]

    def _fstring_to_cout(self, node: ast.JoinedStr) -> str:
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(f'"{value.value}"')
            elif isinstance(value, ast.FormattedValue):
                parts.append(self._expr_to_cpp(value.value))
        return " << ".join(parts)

    def _convert_if(self, node: ast.If) -> list[str]:
        self.patterns_used.append("P014")
        lines = []
        test = self._expr_to_cpp(node.test)
        lines.append(f"{self.indent()}if ({test}) {{")
        self.indent_level += 1
        lines.extend(self._convert_body(node.body))
        self.indent_level -= 1

        # Walk the elif chain iteratively
        current = node
        while current.orelse:
            if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                self.patterns_used.append("P015")
                elif_node = current.orelse[0]
                elif_test = self._expr_to_cpp(elif_node.test)
                lines.append(f"{self.indent()}}} else if ({elif_test}) {{")
                self.indent_level += 1
                lines.extend(self._convert_body(elif_node.body))
                self.indent_level -= 1
                current = elif_node
            else:
                self.patterns_used.append("P015")
                lines.append(f"{self.indent()}}} else {{")
                self.indent_level += 1
                lines.extend(self._convert_body(current.orelse))
                self.indent_level -= 1
                break

        lines.append(f"{self.indent()}}}")
        return lines

    def _convert_for(self, node: ast.For) -> list[str]:
        lines = []
        target = node.target

        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
            args = node.iter.args
            var = self._expr_to_cpp(target)
            if len(args) == 1:
                self.patterns_used.append("P010")
                end = self._expr_to_cpp(args[0])
                lines.append(f"{self.indent()}for (int {var} = 0; {var} < {end}; {var}++) {{")
            elif len(args) == 2:
                self.patterns_used.append("P011")
                start = self._expr_to_cpp(args[0])
                end = self._expr_to_cpp(args[1])
                lines.append(f"{self.indent()}for (int {var} = {start}; {var} < {end}; {var}++) {{")
            elif len(args) == 3:
                start = self._expr_to_cpp(args[0])
                end = self._expr_to_cpp(args[1])
                step = self._expr_to_cpp(args[2])
                lines.append(f"{self.indent()}for (int {var} = {start}; {var} < {end}; {var} += {step}) {{")
        else:
            self.patterns_used.append("P012")
            var = self._expr_to_cpp(target)
            iterable = self._expr_to_cpp(node.iter)
            lines.append(f"{self.indent()}for (auto& {var} : {iterable}) {{")

        self.indent_level += 1
        lines.extend(self._convert_body(node.body))
        self.indent_level -= 1
        lines.append(f"{self.indent()}}}")
        return lines

    def _convert_while(self, node: ast.While) -> list[str]:
        self.patterns_used.append("P013")
        test = self._expr_to_cpp(node.test)
        lines = [f"{self.indent()}while ({test}) {{"]
        self.indent_level += 1
        lines.extend(self._convert_body(node.body))
        self.indent_level -= 1
        lines.append(f"{self.indent()}}}")
        return lines

    def _convert_function(self, node: ast.FunctionDef) -> list[str]:
        ret_type = infer_return_type(node)
        params = []
        for arg in node.args.args:
            if arg.annotation:
                ptype = annotation_to_cpp(arg.annotation)
            else:
                ptype = "auto"
            params.append(f"{ptype} {arg.arg}")

        if node.returns:
            self.patterns_used.append("P017")
        else:
            self.patterns_used.append("P016")
            if ret_type == "void":
                self.patterns_used.append("P018")

        param_str = ", ".join(params)
        lines = [f"{self.indent()}{ret_type} {node.name}({param_str}) {{"]
        self.indent_level += 1
        lines.extend(self._convert_body(node.body))
        self.indent_level -= 1
        lines.append(f"{self.indent()}}}")
        return lines

    def _convert_return(self, node: ast.Return) -> list[str]:
        if node.value is None:
            return [f"{self.indent()}return;"]
        return [f"{self.indent()}return {self._expr_to_cpp(node.value)};"]

    def _is_main_guard(self, node: ast.If) -> bool:
        if isinstance(node.test, ast.Compare):
            left = node.test.left
            if isinstance(left, ast.Name) and left.id == "__name__":
                return True
        return False

    def _convert_main_guard(self, node: ast.If) -> list[str]:
        self.patterns_used.append("P030")
        lines = ["int main() {"]
        self.indent_level = 1
        lines.extend(self._convert_body(node.body))
        self.indent_level = 0
        lines.append("    return 0;")
        lines.append("}")
        return lines

    def _expr_to_cpp(self, node: ast.expr) -> str:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return "true" if node.value else "false"
            if isinstance(node.value, str):
                return f'"{node.value}"'
            return str(node.value)

        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.BinOp):
            left = self._expr_to_cpp(node.left)
            right = self._expr_to_cpp(node.right)
            if isinstance(node.op, ast.Pow):
                self.headers.add("<cmath>")
                self.patterns_used.append("P020")
                return f"pow({left}, {right})"
            if isinstance(node.op, ast.FloorDiv):
                self.patterns_used.append("P021")
                return f"({left} / {right})"
            op_map = {
                ast.Add: "+", ast.Sub: "-", ast.Mult: "*",
                ast.Div: "/", ast.Mod: "%",
            }
            op = op_map.get(type(node.op), "+")
            return f"({left} {op} {right})"

        if isinstance(node, ast.UnaryOp):
            operand = self._expr_to_cpp(node.operand)
            if isinstance(node.op, ast.Not):
                self.patterns_used.append("P019")
                return f"!{operand}"
            if isinstance(node.op, ast.USub):
                return f"-{operand}"
            return operand

        if isinstance(node, ast.BoolOp):
            self.patterns_used.append("P019")
            op = " && " if isinstance(node.op, ast.And) else " || "
            parts = [self._expr_to_cpp(v) for v in node.values]
            return f"({op.join(parts)})"

        if isinstance(node, ast.Compare):
            left = self._expr_to_cpp(node.left)
            parts = [left]
            cmp_map = {
                ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<",
                ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=",
            }
            for op, comparator in zip(node.ops, node.comparators):
                op_str = cmp_map.get(type(op), "==")
                parts.append(f"{op_str} {self._expr_to_cpp(comparator)}")
            return " ".join(parts)

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                args = [self._expr_to_cpp(a) for a in node.args]

                if func_name == "len":
                    self.patterns_used.append("P023")
                    return f"{args[0]}.size()"
                if func_name == "print":
                    return f'cout << {" << ".join(args)} << endl'
                if func_name in ("int", "float", "str"):
                    cast_map = {"int": "int", "float": "double", "str": "string"}
                    return f"static_cast<{cast_map[func_name]}>({args[0]})"
                if func_name == "range":
                    return f"/* range({', '.join(args)}) */"
                if func_name == "abs":
                    self.headers.add("<cmath>")
                    return f"abs({args[0]})"
                if func_name == "max":
                    return f"max({', '.join(args)})"
                if func_name == "min":
                    return f"min({', '.join(args)})"

                return f"{func_name}({', '.join(args)})"

            if isinstance(node.func, ast.Attribute):
                obj = self._expr_to_cpp(node.func.value)
                method = node.func.attr
                args = [self._expr_to_cpp(a) for a in node.args]

                if method == "append":
                    return f"{obj}.push_back({', '.join(args)})"
                if method == "upper":
                    return f"/* {obj}.upper() — use transform */"
                if method == "lower":
                    return f"/* {obj}.lower() — use transform */"

                return f"{obj}.{method}({', '.join(args)})"

        if isinstance(node, ast.List):
            elts = [self._expr_to_cpp(e) for e in node.elts]
            self.headers.add("<vector>")
            return "{" + ", ".join(elts) + "}"

        if isinstance(node, ast.Dict):
            pairs = []
            for k, v in zip(node.keys, node.values):
                pairs.append(f"{{{self._expr_to_cpp(k)}, {self._expr_to_cpp(v)}}}")
            self.headers.add("<map>")
            return "{" + ", ".join(pairs) + "}"

        if isinstance(node, ast.Subscript):
            value = self._expr_to_cpp(node.value)
            sl = self._expr_to_cpp(node.slice)
            self.patterns_used.append("P025")
            return f"{value}[{sl}]"

        if isinstance(node, ast.Attribute):
            value = self._expr_to_cpp(node.value)
            return f"{value}.{node.attr}"

        if isinstance(node, ast.JoinedStr):
            return self._fstring_to_cout(node)

        if isinstance(node, ast.FormattedValue):
            return self._expr_to_cpp(node.value)

        if isinstance(node, ast.IfExp):
            test = self._expr_to_cpp(node.test)
            body = self._expr_to_cpp(node.body)
            orelse = self._expr_to_cpp(node.orelse)
            return f"({test} ? {body} : {orelse})"

        return f"/* unsupported: {type(node).__name__} */"


def convert_python_to_cpp(python_code: str) -> dict:
    converter = PythonToCppConverter()
    result = converter.convert(python_code)
    return {
        "cpp_code": result.cpp_code,
        "patterns_used": result.patterns_used,
        "warnings": result.warnings,
        "headers": list(result.headers_needed),
    }


if __name__ == "__main__":
    test = '''
x = 10
y = 3.14
name = "world"
nums = [1, 2, 3, 4, 5]

def add(a: int, b: int) -> int:
    return a + b

for i in range(x):
    if i > 5:
        print(f"big: {i}")
    else:
        print(i)

result = add(x, 3)
print(result)

for n in nums:
    print(n ** 2)
'''
    result = convert_python_to_cpp(test)
    print(result["cpp_code"])
    print(f"\nPatterns used: {result['patterns_used']}")
    if result["warnings"]:
        print(f"Warnings: {result['warnings']}")
