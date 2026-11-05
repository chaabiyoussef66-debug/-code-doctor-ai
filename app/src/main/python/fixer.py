"""Conservative, offline code repair suggestions for Code Doctor AI.

Only applies a narrow, deterministic repair when a simple constant assignment
in a function appears after a straight-line read of the same local variable.
It never executes submitted code.
"""
import ast
import json


class _DirectNames(ast.NodeVisitor):
    """Collect names in a statement without entering nested lexical scopes."""
    def __init__(self):
        self.loads = set()
        self.stores = set()
        self.globals = set()
        self.nonlocals = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.loads.add(node.id)
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            self.stores.add(node.id)

    def visit_FunctionDef(self, node):
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        return

    def visit_Lambda(self, node):
        return

    def visit_Global(self, node):
        self.globals.update(node.names)

    def visit_Nonlocal(self, node):
        self.nonlocals.update(node.names)


def _simple_constant_assignment(statement):
    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
        return None
    target = statement.targets[0]
    if not isinstance(target, ast.Name) or not isinstance(statement.value, ast.Constant):
        return None
    if getattr(statement, "lineno", None) != getattr(statement, "end_lineno", None):
        return None
    return target.id


def _find_safe_reorder(tree):
    """Return (read_line, assignment_line, name) for a very narrow safe case."""
    functions = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for function in functions:
        body = function.body
        args = function.args
        parameters = {
            arg.arg for arg in
            args.posonlyargs + args.args + args.kwonlyargs
        }
        if args.vararg:
            parameters.add(args.vararg.arg)
        if args.kwarg:
            parameters.add(args.kwarg.arg)
        declarations = _DirectNames()
        for item in body:
            declarations.visit(item)
        for write_index, statement in enumerate(body):
            name = _simple_constant_assignment(statement)
            if not name or name in parameters:
                continue
            if name in declarations.globals or name in declarations.nonlocals:
                continue
            # Do not move an assignment past any earlier write to this name.
            prior_write = False
            for earlier in body[:write_index]:
                names = _DirectNames()
                names.visit(earlier)
                if name in names.stores:
                    prior_write = True
                    break
            if prior_write:
                continue

            for read_index, earlier in enumerate(body[:write_index]):
                names = _DirectNames()
                names.visit(earlier)
                if name not in names.loads:
                    continue
                # Moving across branches, loops, exception handlers, or other
                # compound statements could change program semantics.
                segment = body[read_index:write_index + 1]
                if any(not isinstance(item, (ast.Expr, ast.Assign, ast.AnnAssign, ast.Pass))
                       for item in segment):
                    continue
                if any(
                    name in _DirectNamesFor(item).stores
                    for item in body[read_index:write_index]
                ):
                    continue
                return earlier.lineno, statement.lineno, name
    return None


def _DirectNamesFor(node):
    visitor = _DirectNames()
    visitor.visit(node)
    return visitor



class _DirectLoadNodes(_DirectNames):
    def __init__(self):
        super().__init__()
        self.nodes = []

    def visit_Name(self, node):
        super().visit_Name(node)
        if isinstance(node.ctx, ast.Load):
            self.nodes.append(node)


def _find_safe_name_typo(tree):
    """Find one unambiguous misspelled local/builtin name in a function."""
    import builtins
    from difflib import SequenceMatcher

    def similarity(left, right):
        if len(left) == len(right):
            differences = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
            if (len(differences) == 2
                    and differences[1] == differences[0] + 1
                    and left[differences[0]] == right[differences[1]]
                    and left[differences[1]] == right[differences[0]]):
                # Treat one adjacent transposition as a likely typing slip.
                return 0.90
        return SequenceMatcher(None, left, right).ratio()

    matches = []
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        visitor = _DirectNames()
        for statement in function.body:
            visitor.visit(statement)
        args = function.args
        parameters = {
            arg.arg for arg in
            args.posonlyargs + args.args + args.kwonlyargs
        }
        if args.vararg:
            parameters.add(args.vararg.arg)
        if args.kwarg:
            parameters.add(args.kwarg.arg)
        if visitor.globals or visitor.nonlocals:
            # Avoid guessing across explicit scope declarations.
            continue
        candidates = (visitor.stores | parameters | set(dir(builtins)))
        loads = _DirectLoadNodes()
        for statement in function.body:
            loads.visit(statement)
        for node in loads.nodes:
                if node.id in candidates or len(node.id) < 3:
                    continue
                scored = sorted(
                    ((similarity(node.id, name), name)
                     for name in candidates if len(name) >= 3),
                    reverse=True
                )
                if not scored:
                    continue
                best_score, best_name = scored[0]
                second_score = scored[1][0] if len(scored) > 1 else 0.0
                if best_score >= 0.78 and best_score - second_score >= 0.10:
                    matches.append((node, best_name))
    # Only offer one typo correction at a time; multiple guesses are ambiguous.
    return matches[0] if len(matches) == 1 else None


def _replace_name_at_node(source, node, replacement):
    lines = source.splitlines(keepends=True)
    line_index = node.lineno - 1
    if not (0 <= line_index < len(lines)):
        return None
    raw = lines[line_index].encode("utf-8")
    start = node.col_offset
    end = node.end_col_offset
    try:
        found = raw[start:end].decode("utf-8")
    except UnicodeDecodeError:
        return None
    if found != node.id:
        return None
    lines[line_index] = (
        raw[:start] + replacement.encode("utf-8") + raw[end:]
    ).decode("utf-8")
    return "".join(lines)


def fix_code(source):
    """Return a preview of a conservative repair; never run source code."""
    # Prefer narrow Flask security repairs before the existing generic repairs.
    from security_fixer import fix_flask_security
    security_result = fix_flask_security(source)
    if security_result is not None:
        return security_result
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return json.dumps({
            "can_apply": False,
            "fixed_code": source,
            "changes": [],
            "message": "تعذر اقتراح إصلاح آلي لأن الكود يحتوي على خطأ في الصياغة قرب السطر "
                       + str(exc.lineno or 1) + ". صحح الصياغة أولاً."
        }, ensure_ascii=False)

    candidate = _find_safe_reorder(tree)
    if candidate is None:
        typo = _find_safe_name_typo(tree)
        if typo is not None:
            node, replacement = typo
            fixed = _replace_name_at_node(source, node, replacement)
            if fixed is not None:
                try:
                    ast.parse(fixed)
                    compile(fixed, "<code-doctor-typo-preview>", "exec")
                except (SyntaxError, ValueError, TypeError):
                    fixed = None
            if fixed is not None:
                return json.dumps({
                    "can_apply": True,
                    "fixed_code": fixed,
                    "changes": [{
                        "line": node.lineno,
                        "title": "تصحيح اسم قريب من متغير أو دالة معرّفة",
                        "message": "تم اقتراح استبدال '" + node.id + "' بـ '" + replacement + "' لأن التطابق واضح."
                    }],
                    "message": "اقتراح مبني على تشابه الاسم مع اسم معروف في النطاق. راجع المعاينة قبل التطبيق؛ قد يكون الاسم مقصوداً."
                }, ensure_ascii=False)
        return json.dumps({
            "can_apply": False,
            "fixed_code": source,
            "changes": [],
            "message": "لم أجد إصلاحاً آلياً آمناً ضمن القواعد الحالية. لم أغيّر الكود. "
                       "راجع اقتراحات الفحص أو أصلح الحالة يدوياً."
        }, ensure_ascii=False)

    read_line, assignment_line, name = candidate
    lines = source.splitlines(keepends=True)
    if not (1 <= read_line <= len(lines) and 1 <= assignment_line <= len(lines)):
        return json.dumps({
            "can_apply": False, "fixed_code": source, "changes": [],
            "message": "تعذر تحديد موضع الإصلاح بأمان؛ لم يتغير الكود."
        }, ensure_ascii=False)

    assignment = lines[assignment_line - 1]
    # Keep the repair conservative: do not move comments or blank lines.
    if not assignment.strip() or assignment.lstrip().startswith("#"):
        return json.dumps({
            "can_apply": False, "fixed_code": source, "changes": [],
            "message": "موضع التعيين غير مناسب للإصلاح الآلي؛ لم يتغير الكود."
        }, ensure_ascii=False)

    del lines[assignment_line - 1]
    lines.insert(read_line - 1, assignment)
    fixed = "".join(lines)
    try:
        ast.parse(fixed)
        compile(fixed, "<code-doctor-fixed-preview>", "exec")
    except (SyntaxError, ValueError, TypeError):
        return json.dumps({
            "can_apply": False, "fixed_code": source, "changes": [],
            "message": "فشل التحقق من النسخة المقترحة؛ احتفظت بالكود الأصلي دون تغيير."
        }, ensure_ascii=False)

    return json.dumps({
        "can_apply": True,
        "fixed_code": fixed,
        "changes": [{
            "line": read_line,
            "title": "نقل تهيئة المتغير قبل أول استعمال",
            "message": "تم نقل تعيين المتغير '" + name
                       + "' إلى ما قبل قراءته في مسار متتابع بسيط."
        }],
        "message": "اقتراح إصلاح محدود وآمن لهذه الحالة. راجع النسخة قبل تطبيقها؛ "
                   "نجاح التحليل لا يضمن صحة منطق البرنامج بالكامل."
    }, ensure_ascii=False)
