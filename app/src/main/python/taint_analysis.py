"""Conservative, intraprocedural taint-flow checks for untrusted Python input.

This module is deliberately static: it parses AST nodes and never executes user code.
It tracks simple aliases and branch merges, then reports only when tainted values
reach high-risk sinks.
"""
import ast
import re


SQL_PATTERN = re.compile(r"(?i)\b(select|insert|update|delete|replace)\b")
SQL_SINKS = {"execute", "executemany"}
SHELL_CALLS = {"run", "Popen", "call", "check_call", "check_output"}


def _attribute_parts(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return list(reversed(parts))
    return []


def _is_untrusted_source(node):
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name) and node.func.id == "input":
        return True
    parts = _attribute_parts(node.func)
    if not parts or parts[0] != "request":
        return False
    path = parts[1:]
    return (
        path == ["get_json"]
        or (len(path) >= 2 and path[0] in {"args", "form", "values", "json"})
    )


def _target_names(target):
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names = set()
        for item in target.elts:
            names.update(_target_names(item))
        return names
    return set()


class TaintFlowVisitor(ast.NodeVisitor):
    """Track may-be-tainted names in one lexical scope, without crossing functions."""

    def __init__(self, tainted=None):
        self.tainted = set(tainted or ())
        self.issues = []

    def is_tainted(self, node):
        if node is None:
            return False
        if isinstance(node, ast.Name):
            return node.id in self.tainted
        if _is_untrusted_source(node):
            return True
        if isinstance(node, ast.Constant):
            return False
        if isinstance(node, ast.JoinedStr):
            return any(self.is_tainted(value) for value in node.values)
        if isinstance(node, ast.FormattedValue):
            return self.is_tainted(node.value)
        if isinstance(node, ast.BinOp):
            return self.is_tainted(node.left) or self.is_tainted(node.right)
        if isinstance(node, ast.BoolOp):
            return any(self.is_tainted(value) for value in node.values)
        if isinstance(node, ast.Compare):
            return self.is_tainted(node.left) or any(
                self.is_tainted(value) for value in node.comparators
            )
        if isinstance(node, ast.Subscript):
            return self.is_tainted(node.value) or self.is_tainted(node.slice)
        if isinstance(node, ast.Call):
            return _is_untrusted_source(node) or any(
                self.is_tainted(arg) for arg in node.args
            ) or any(self.is_tainted(keyword.value) for keyword in node.keywords)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return any(self.is_tainted(item) for item in node.elts)
        if isinstance(node, ast.Dict):
            return any(
                self.is_tainted(key) or self.is_tainted(value)
                for key, value in zip(node.keys, node.values)
            )
        if isinstance(node, ast.UnaryOp):
            return self.is_tainted(node.operand)
        return False

    def report(self, node, title, message, suggestion):
        self.issues.append({
            "severity": "WARNING",
            "title": title,
            "line": getattr(node, "lineno", 1),
            "message": message,
            "suggestion": suggestion,
            "confidence": "POTENTIAL",
        })

    def _check_sink(self, node):
        func = node.func
        parts = _attribute_parts(func)
        name = func.id if isinstance(func, ast.Name) else (parts[-1] if parts else "")

        if isinstance(func, ast.Name) and name in {"eval", "exec"}:
            if node.args and self.is_tainted(node.args[0]):
                self.report(
                    node, "مدخلات غير موثوقة تصل إلى تنفيذ Python ديناميكي",
                    "قيمة مصدرها إدخال المستخدم قد تصل إلى " + name + "؛ قد يسمح ذلك بحقن تعليمات Python.",
                    "تجنب eval وexec مع مدخلات المستخدم؛ استعمل محللاً أو بنية بيانات محددة."
                )

        if parts and parts[0] == "os" and name == "system":
            if node.args and self.is_tainted(node.args[0]):
                self.report(
                    node, "مدخلات غير موثوقة تصل إلى أمر نظام",
                    "نص متأثر بمدخلات المستخدم يصل إلى os.system وقد يسبب حقن أوامر.",
                    "تجنب os.system؛ استعمل subprocess بوسائط منفصلة وتحقق من كل قيمة."
                )

        if parts and parts[0] == "subprocess" and name in SHELL_CALLS:
            shell_enabled = any(
                item.arg == "shell" and isinstance(item.value, ast.Constant)
                and item.value.value is True for item in node.keywords
            )
            if shell_enabled and node.args and self.is_tainted(node.args[0]):
                self.report(
                    node, "مدخلات غير موثوقة تصل إلى subprocess مع shell=True",
                    "أمر shell يحتوي على قيمة متأثرة بمدخلات المستخدم؛ قد يسمح بحقن أوامر.",
                    "استعمل قائمة وسائط مع shell=False ولا تدمج مدخلات المستخدم في نص الأمر."
                )

        if parts and name in SQL_SINKS and node.args:
            query = node.args[0]
            contains_sql = any(
                isinstance(item, ast.Constant) and isinstance(item.value, str)
                and SQL_PATTERN.search(item.value)
                for item in ast.walk(query)
            )
            if contains_sql and self.is_tainted(query):
                self.report(
                    node, "مدخلات غير موثوقة تصل إلى استعلام SQL",
                    "قيمة متأثرة بمدخلات المستخدم تصل إلى استعلام SQL مركب ديناميكياً؛ قد يحدث SQL injection.",
                    "استعمل معاملات SQL المعلّمة placeholders ولا تدمج القيم داخل نص الاستعلام."
                )

    def visit_Call(self, node):
        self._check_sink(node)
        self.generic_visit(node)

    def visit_Assign(self, node):
        tainted = self.is_tainted(node.value)
        self.visit(node.value)
        for target in node.targets:
            names = _target_names(target)
            if tainted:
                self.tainted.update(names)
            else:
                self.tainted.difference_update(names)
            self.visit(target)

    def visit_AnnAssign(self, node):
        if node.annotation:
            self.visit(node.annotation)
        tainted = self.is_tainted(node.value)
        if node.value:
            self.visit(node.value)
        names = _target_names(node.target)
        if node.value is not None and not tainted:
            self.tainted.difference_update(names)
        elif tainted:
            self.tainted.update(names)
        self.visit(node.target)

    def visit_AugAssign(self, node):
        tainted = self.is_tainted(node.target) or self.is_tainted(node.value)
        self.visit(node.value)
        names = _target_names(node.target)
        if tainted:
            self.tainted.update(names)
        self.visit(node.target)

    def visit_NamedExpr(self, node):
        tainted = self.is_tainted(node.value)
        self.visit(node.value)
        names = _target_names(node.target)
        if tainted:
            self.tainted.update(names)
        else:
            self.tainted.difference_update(names)

    def _branch(self, statements, initial):
        child = TaintFlowVisitor(initial)
        for statement in statements:
            child.visit(statement)
        self.issues.extend(child.issues)
        return child.tainted

    def visit_If(self, node):
        self.visit(node.test)
        before = set(self.tainted)
        body_state = self._branch(node.body, before)
        else_state = self._branch(node.orelse, before)
        self.tainted = body_state | else_state

    def visit_For(self, node):
        self.visit(node.iter)
        before = set(self.tainted)
        body_state = self._branch(node.body, before)
        else_state = self._branch(node.orelse, before | _target_names(node.target))
        self.tainted = before | body_state | else_state

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        self.visit(node.test)
        before = set(self.tainted)
        body_state = self._branch(node.body, before)
        else_state = self._branch(node.orelse, before)
        self.tainted = before | body_state | else_state

    def visit_FunctionDef(self, node):
        # Defaults/decorators execute in the enclosing scope; the body has its own locals.
        for item in node.decorator_list:
            self.visit(item)
        for item in node.args.defaults + node.args.kw_defaults:
            if item is not None:
                self.visit(item)
        child = TaintFlowVisitor()
        for statement in node.body:
            child.visit(statement)
        self.issues.extend(child.issues)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        for item in node.args.defaults + node.args.kw_defaults:
            if item is not None:
                self.visit(item)

    def visit_ClassDef(self, node):
        for item in node.decorator_list + node.bases:
            self.visit(item)
        child = TaintFlowVisitor()
        for statement in node.body:
            child.visit(statement)
        self.issues.extend(child.issues)


def analyze_tainted_flows(tree):
    visitor = TaintFlowVisitor()
    visitor.visit(tree)
    return visitor.issues
