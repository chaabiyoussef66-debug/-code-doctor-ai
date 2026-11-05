"""Offline Python analyzer. Parses submitted source; never executes it."""
import ast
import builtins
import json
import re

SECRET = re.compile(r"""(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*['"][^'"]{8,}['"]""")

def issue(severity, title, node, message, suggestion, confidence="CONFIRMED"):
    return {
        "severity": severity, "title": title,
        "line": getattr(node, "lineno", 1),
        "message": message, "suggestion": suggestion,
        "confidence": confidence
    }

def literal(node):
    """Return (known, value) for safe, side-effect-free literal containers."""
    if isinstance(node, ast.Constant):
        return True, node.value
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = []
        for item in node.elts:
            known, value = literal(item)
            if not known:
                return False, None
            values.append(value)
        return True, values if isinstance(node, ast.List) else tuple(values) if isinstance(node, ast.Tuple) else set(values)
    if isinstance(node, ast.Dict):
        pairs = []
        for key, value_node in zip(node.keys, node.values):
            if key is None:
                return False, None
            k_ok, k = literal(key)
            v_ok, v = literal(value_node)
            if not (k_ok and v_ok):
                return False, None
            pairs.append((k, v))
        try:
            return True, dict(pairs)
        except (TypeError, ValueError):
            return False, None
    return False, None

class BindingCollector(ast.NodeVisitor):
    """Collect names bound in one scope, excluding child lexical scopes."""
    def __init__(self):
        self.names = set()
        self.globals = set()
        self.nonlocals = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Param)):
            self.names.add(node.id)

    def visit_Global(self, node):
        self.globals.update(node.names)

    def visit_Nonlocal(self, node):
        self.nonlocals.update(node.names)

    def visit_FunctionDef(self, node):
        self.names.add(node.name)
        args = node.args
        for arg in args.posonlyargs + args.args + args.kwonlyargs:
            self.names.add(arg.arg)
        if args.vararg:
            self.names.add(args.vararg.arg)
        if args.kwarg:
            self.names.add(args.kwarg.arg)
        self.generic_visit(node)
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.names.add(node.name)
        self.generic_visit(node)

    def visit_Lambda(self, node):
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            self.names.add(arg.arg)
        if node.args.vararg:
            self.names.add(node.args.vararg.arg)
        if node.args.kwarg:
            self.names.add(node.args.kwarg.arg)
        self.generic_visit(node)

    def visit_ListComp(self, node):
        self.generic_visit(node)
    visit_SetComp = visit_ListComp
    visit_DictComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp

class NameUseVisitor(ast.NodeVisitor):
    def __init__(self, known_names, local_names, globals_declared, line_issues):
        self.known_names = known_names
        self.local_names = local_names
        self.globals_declared = globals_declared
        self.line_issues = line_issues

    def visit_Name(self, node):
        if not isinstance(node.ctx, ast.Load):
            return
        name = node.id
        if name in self.known_names or name in self.local_names or name in self.globals_declared:
            return
        if hasattr(builtins, name):
            return
        self.line_issues.append(issue(
            "ERROR", "اسم أو متغير غير معرّف", node,
            "الاسم '" + name + "' يُستعمل دون تعريف أو استيراد ظاهر؛ قد يسبب NameError.",
            "عرّف المتغير قبل استعماله، أو صحح الاسم، أو أضف الاستيراد اللازم."
        ))

class Inspector(ast.NodeVisitor):
    def __init__(self):
        self.issues = []
        self.constants = {}
        self.function_depth = 0
        self.class_scope_stack = []

    def add(self, severity, title, node, message, suggestion, confidence="CONFIRMED"):
        self.issues.append(issue(severity, title, node, message, suggestion, confidence))

    def resolve_literal(self, node):
        known, value = literal(node)
        if known:
            return True, value
        if isinstance(node, ast.Name) and node.id in self.constants:
            return True, self.constants[node.id]
        return False, None

    def visit_Assign(self, node):
        self.visit(node.value)
        known, value = self.resolve_literal(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                if known:
                    self.constants[target.id] = value
                else:
                    self.constants.pop(target.id, None)
            else:
                self.visit(target)

    def visit_AnnAssign(self, node):
        if node.value is not None:
            self.visit(node.value)
            known, value = self.resolve_literal(node.value)
            if isinstance(node.target, ast.Name):
                if known:
                    self.constants[node.target.id] = value
                else:
                    self.constants.pop(node.target.id, None)
        self.visit(node.target)

    def visit_AugAssign(self, node):
        self.visit(node.value)
        if isinstance(node.target, ast.Name):
            self.constants.pop(node.target.id, None)
        self.visit(node.target)

    def known_condition(self, node):
        """Evaluate only simple conditions whose operands are known literals."""
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return True, node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            known, value = self.known_condition(node.operand)
            return (True, not value) if known else (False, None)
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
            left_known, left = self.resolve_literal(node.left)
            right_known, right = self.resolve_literal(node.comparators[0])
            if not (left_known and right_known):
                return False, None
            op = node.ops[0]
            try:
                if isinstance(op, ast.Eq):
                    return True, left == right
                if isinstance(op, ast.NotEq):
                    return True, left != right
                if isinstance(op, ast.Lt):
                    return True, left < right
                if isinstance(op, ast.LtE):
                    return True, left <= right
                if isinstance(op, ast.Gt):
                    return True, left > right
                if isinstance(op, ast.GtE):
                    return True, left >= right
                if isinstance(op, ast.Is):
                    return True, left is right
                if isinstance(op, ast.IsNot):
                    return True, left is not right
                if isinstance(op, ast.In):
                    return True, left in right
                if isinstance(op, ast.NotIn):
                    return True, left not in right
            except (TypeError, ValueError):
                return False, None
        return False, None

    def visit_If(self, node):
        # Analyze the condition first, then skip branches proven unreachable.
        self.visit(node.test)
        known, condition = self.known_condition(node.test)
        if known:
            for statement in (node.body if condition else node.orelse):
                self.visit(statement)
            return
        # For an unknown condition, analyze both paths independently and keep
        # only constants that agree on both paths.
        before = dict(self.constants)
        for statement in node.body:
            self.visit(statement)
        body_constants = dict(self.constants)
        self.constants = dict(before)
        for statement in node.orelse:
            self.visit(statement)
        else_constants = dict(self.constants)
        self.constants = {
            name: value for name, value in body_constants.items()
            if name in else_constants and type(value) is type(else_constants[name]) and value == else_constants[name]
        }

    def visit_BinOp(self, node):
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            known, value = self.resolve_literal(node.right)
            if known and isinstance(value, (int, float, complex)) and not isinstance(value, bool) and value == 0:
                self.add("ERROR", "قسمة على صفر", node,
                    "المقام قيمة ثابتة تساوي صفراً؛ العملية ستطلق ZeroDivisionError.",
                    "تحقق من المقام قبل القسمة أو عالج حالة الصفر.")
        left_known, left = self.resolve_literal(node.left)
        right_known, right = self.resolve_literal(node.right)
        if left_known and right_known:
            bad = False
            if isinstance(node.op, ast.Add):
                bad = not ((isinstance(left, (int, float, complex)) and not isinstance(left, bool) and isinstance(right, (int, float, complex)) and not isinstance(right, bool)) or (type(left) is type(right) and isinstance(left, (str, list, tuple))))
            elif isinstance(node.op, ast.Mult):
                numeric_pair = (isinstance(left, (int, float, complex)) and not isinstance(left, bool) and isinstance(right, (int, float, complex)) and not isinstance(right, bool))
                sequence_repeat = ((isinstance(left, (str, list, tuple, bytes)) and isinstance(right, int) and not isinstance(right, bool)) or (isinstance(right, (str, list, tuple, bytes)) and isinstance(left, int) and not isinstance(left, bool)))
                bad = not (numeric_pair or sequence_repeat)
            elif isinstance(node.op, (ast.Sub, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
                bad = not (isinstance(left, (int, float, complex)) and not isinstance(left, bool) and isinstance(right, (int, float, complex)) and not isinstance(right, bool))
            if bad:
                self.add("ERROR", "تعارض أنواع البيانات", node,
                    "العملية بين قيم ثابتة من أنواع غير متوافقة؛ قد تسبب TypeError.",
                    "حوّل القيم إلى أنواع متوافقة أو راجع العملية.")
        self.generic_visit(node)

    def visit_Subscript(self, node):
        known, value = self.resolve_literal(node.value)
        index_known, index = self.resolve_literal(node.slice)
        if known and index_known and isinstance(value, (list, tuple, str, bytes)):
            if isinstance(index, int) and not isinstance(index, bool):
                if index >= len(value) or index < -len(value):
                    self.add("ERROR", "فهرس خارج الحدود", node,
                        "الفهرس " + str(index) + " خارج طول العنصر (" + str(len(value)) + ")؛ سيحدث IndexError.",
                        "استعمل فهرساً بين -" + str(len(value)) + " و" + str(max(0, len(value)-1)) + " أو تحقق من الطول.")
        if known and not isinstance(value, (list, tuple, str, bytes, dict)) and index_known:
            self.add("ERROR", "نوع لا يدعم الفهرسة", node,
                "القيمة الثابتة من النوع " + type(value).__name__ + " لا تدعم الفهرسة؛ سيحدث TypeError.",
                "استعمل نوع بيانات قابلاً للفهرسة أو غيّر طريقة الوصول.")
        self.generic_visit(node)

    def visit_Call(self, node):
        name = node.func.id if isinstance(node.func, ast.Name) else (node.func.attr if isinstance(node.func, ast.Attribute) else None)
        warnings = {
            "eval": ("استعمال eval", "قد ينفذ تعبيراً غير موثوق.", "تجنب eval واستعمل parsing آمناً."),
            "exec": ("استعمال exec", "قد ينفذ نصاً كتعليمات Python.", "تجنب exec ولا تمرر إليه مدخلات غير موثوقة."),
            "system": ("استدعاء system", "أوامر النظام تحتاج مراجعة المدخلات.", "تجنب shell مع نصوص غير موثوقة."),
            "loads": ("فك تسلسل بيانات", "بعض دوال loads مثل pickle قد تكون خطيرة مع بيانات غير موثوقة.", "استعمل تنسيقاً آمناً مثل JSON عند الإمكان.")
        }
        if name in warnings:
            title, msg, fix = warnings[name]
            self.add("WARNING", title, node, msg, fix, "POTENTIAL")
        if isinstance(node.func, ast.Name) and node.func.id == "len" and node.args:
            known, value = literal(node.args[0])
            if known and isinstance(value, (int, float, complex, bool)):
                self.add("ERROR", "نوع غير صالح للدالة len", node,
                    "الدالة len لا تقبل قيمة عددية ثابتة؛ سيحدث TypeError.",
                    "مرر سلسلة أو قائمة أو كائناً يدعم len().")
        if isinstance(node.func, ast.Attribute) and node.func.attr == "load" and isinstance(node.func.value, ast.Name) and node.func.value.id == "yaml":
            safe = any(k.arg == "Loader" and isinstance(k.value, ast.Attribute) and k.value.attr == "SafeLoader" for k in node.keywords)
            if not safe:
                self.add("WARNING", "yaml.load يحتاج Loader آمن", node,
                    "yaml.load دون SafeLoader قد يكون خطيراً مع بيانات غير موثوقة.",
                    "استعمل yaml.safe_load للبيانات غير الموثوقة.", "POTENTIAL")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if node.type is None:
            self.add("INFO", "except عام", node,
                "التقاط جميع الاستثناءات قد يخفي أخطاء غير متوقعة.",
                "حدد أنواع الاستثناءات المتوقعة وسجل الخطأ عند الحاجة.", "POTENTIAL")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Signature expressions run in the enclosing scope.
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.add("WARNING", "قيمة افتراضية قابلة للتغيير", default,
                    "القيمة الافتراضية تُشارك بين استدعاءات الدالة.",
                    "استعمل None وأنشئ القيمة داخل الدالة.", "POTENTIAL")
            self.visit(default)
        for default in node.args.kw_defaults:
            if default is not None:
                self.visit(default)
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            if arg.annotation:
                self.visit(arg.annotation)
        if node.args.vararg and node.args.vararg.annotation:
            self.visit(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation:
            self.visit(node.args.kwarg.annotation)
        if node.returns:
            self.visit(node.returns)

        if self.class_scope_stack and self.function_depth == self.class_scope_stack[-1][1]:
            outer = dict(self.class_scope_stack[-1][0])
        else:
            outer = dict(self.constants)
        collector = LocalBindingCollector()
        for statement in node.body:
            collector.visit(statement)
        local_names = (collector.names - collector.globals - collector.nonlocals) | ScopeNameVisitor.parameters(node.args)
        for name in local_names:
            self.constants.pop(name, None)
        self.function_depth += 1
        for statement in node.body:
            self.visit(statement)
        self.function_depth -= 1
        self.constants = outer

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        for default in node.args.defaults + node.args.kw_defaults:
            if default is not None:
                self.visit(default)
        outer = dict(self.constants)
        for name in ScopeNameVisitor.parameters(node.args):
            self.constants.pop(name, None)
        self.visit(node.body)
        self.constants = outer

    def visit_ClassDef(self, node):
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)
        outer = dict(self.constants)
        self.class_scope_stack.append((outer, self.function_depth))
        for statement in node.body:
            self.visit(statement)
        self.class_scope_stack.pop()
        self.constants = outer

class LocalBindingCollector(ast.NodeVisitor):
    """Collect bindings for a single Python scope without crossing nested scopes."""
    def __init__(self):
        self.names = set()
        self.globals = set()
        self.nonlocals = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Param)):
            self.names.add(node.id)

    def visit_Global(self, node):
        self.globals.update(node.names)

    def visit_Nonlocal(self, node):
        self.nonlocals.update(node.names)

    def visit_FunctionDef(self, node):
        self.names.add(node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.names.add(node.name)

    def visit_Lambda(self, node):
        return

    def visit_Import(self, node):
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name != "*":
                self.names.add(alias.asname or alias.name)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.names.add(node.name)
        if node.type:
            self.visit(node.type)
        for child in node.body:
            self.visit(child)

    def _visit_comprehension(self, node, values):
        # Comprehension targets belong to the comprehension's implicit scope.
        for generator in node.generators:
            self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)
        for value in values:
            self.visit(value)

    def visit_ListComp(self, node):
        self._visit_comprehension(node, [node.elt])

    def visit_SetComp(self, node):
        self._visit_comprehension(node, [node.elt])

    def visit_GeneratorExp(self, node):
        self._visit_comprehension(node, [node.elt])

    def visit_DictComp(self, node):
        self._visit_comprehension(node, [node.key, node.value])


class ScopeNameVisitor(ast.NodeVisitor):
    """Conservative undefined-name checks respecting Python lexical scopes."""
    def __init__(self, available, local_names=None, closure_names=None, scope_kind="module"):
        self.available = set(available)
        self.local_names = set(local_names or ())
        self.closure_names = set(closure_names or ())
        self.scope_kind = scope_kind
        self.issues = []

    @staticmethod
    def parameters(args):
        result = set()
        for arg in args.posonlyargs + args.args + args.kwonlyargs:
            result.add(arg.arg)
        if args.vararg:
            result.add(args.vararg.arg)
        if args.kwarg:
            result.add(args.kwarg.arg)
        return result

    def visit_Name(self, node):
        if not isinstance(node.ctx, ast.Load):
            return
        name = node.id
        if name in self.available or name in self.local_names or name in self.closure_names:
            return
        self.issues.append(issue(
            "ERROR", "اسم أو متغير غير معرّف", node,
            "الاسم '" + name + "' غير معرّف في النطاق الظاهر؛ قد يسبب NameError.",
            "عرّف الاسم قبل استعماله أو صحح كتابته أو أضف الاستيراد اللازم."
        ))

    def _visit_function_signature(self, node):
        # Defaults, decorators and annotations execute in the enclosing scope.
        for item in node.decorator_list:
            self.visit(item)
        for item in node.args.defaults + node.args.kw_defaults:
            if item is not None:
                self.visit(item)
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            if arg.annotation:
                self.visit(arg.annotation)
        if node.args.vararg and node.args.vararg.annotation:
            self.visit(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation:
            self.visit(node.args.kwarg.annotation)
        if node.returns:
            self.visit(node.returns)

    def visit_FunctionDef(self, node):
        self._visit_function_signature(node)
        collector = LocalBindingCollector()
        for statement in node.body:
            collector.visit(statement)
        parameters = self.parameters(node.args)
        globals_bound = collector.names & collector.globals
        locals_for_function = (collector.names - collector.globals - collector.nonlocals) | parameters
        # A method does not close over the containing class namespace.
        enclosing_locals = set() if self.scope_kind == "class" else self.local_names
        child = ScopeNameVisitor(
            self.available | globals_bound,
            locals_for_function,
            self.closure_names | enclosing_locals,
            "function"
        )
        for statement in node.body:
            child.visit(statement)
        self.issues.extend(child.issues)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        for item in node.args.defaults + node.args.kw_defaults:
            if item is not None:
                self.visit(item)
        enclosing_locals = set() if self.scope_kind == "class" else self.local_names
        child = ScopeNameVisitor(
            self.available,
            self.parameters(node.args),
            self.closure_names | enclosing_locals,
            "function"
        )
        child.visit(node.body)
        self.issues.extend(child.issues)

    def visit_ClassDef(self, node):
        for item in node.decorator_list + node.bases:
            self.visit(item)
        for keyword in node.keywords:
            self.visit(keyword.value)
        collector = LocalBindingCollector()
        for statement in node.body:
            collector.visit(statement)
        class_locals = collector.names - collector.globals - collector.nonlocals
        child = ScopeNameVisitor(
            self.available | (collector.names & collector.globals),
            class_locals,
            self.closure_names | self.local_names,
            "class"
        )
        for statement in node.body:
            child.visit(statement)
        self.issues.extend(child.issues)

    def _visit_comprehension(self, node, result_nodes):
        if not node.generators:
            return
        # The first iterable is evaluated in the enclosing scope.
        self.visit(node.generators[0].iter)
        comp_locals = set()
        for generator in node.generators:
            target_collector = LocalBindingCollector()
            target_collector.visit(generator.target)
            comp_locals.update(target_collector.names)
        enclosing_locals = set() if self.scope_kind == "class" else self.local_names
        child = ScopeNameVisitor(
            self.available,
            comp_locals,
            self.closure_names | enclosing_locals,
            "comprehension"
        )
        for index, generator in enumerate(node.generators):
            if index:
                child.visit(generator.iter)
            for condition in generator.ifs:
                child.visit(condition)
        for result_node in result_nodes:
            child.visit(result_node)
        self.issues.extend(child.issues)

    def visit_ListComp(self, node):
        self._visit_comprehension(node, [node.elt])

    def visit_SetComp(self, node):
        self._visit_comprehension(node, [node.elt])

    def visit_GeneratorExp(self, node):
        self._visit_comprehension(node, [node.elt])

    def visit_DictComp(self, node):
        self._visit_comprehension(node, [node.key, node.value])



def analyze(source):
    issues = []
    for number, line in enumerate(source.splitlines(), 1):
        if SECRET.search(line):
            issues.append({
                "severity": "WARNING", "title": "احتمال وجود سر داخل الكود",
                "line": number, "message": "السطر يشبه تعيين كلمة مرور أو مفتاح أو رمز سري.",
                "suggestion": "لا تضع الأسرار داخل الكود؛ استعمل تخزيناً آمناً.",
                "confidence": "POTENTIAL"
            })
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        issues.append(issue("ERROR", "خطأ في صياغة Python", type("N", (), {"lineno": exc.lineno or 1})(),
            exc.msg or "تعذر تحليل الكود.",
            "راجع الأقواس والنقطتين والمسافات قرب السطر المحدد."))
        return json.dumps({"status": "SYNTAX_ERROR", "issues": issues}, ensure_ascii=False)

    inspector = Inspector()
    inspector.visit(tree)
    issues.extend(inspector.issues)

    # Resolve names per lexical scope. A local variable in one function
    # must never make the same name appear defined in another function.
    module_collector = LocalBindingCollector()
    module_collector.visit(tree)
    module_names = module_collector.names | set(dir(builtins))
    name_checker = ScopeNameVisitor(module_names, module_collector.names)
    name_checker.visit(tree)
    issues.extend(name_checker.issues)

    order = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}
    # Remove duplicate reports for the same NameError location.
    unique = {}
    for item in issues:
        key = (item["title"], item["line"], item["message"])
        unique[key] = item
    issues = sorted(unique.values(), key=lambda x: (order.get(x["severity"], 9), x["line"]))
    return json.dumps({
        "status": "ISSUES_FOUND" if issues else "NO_RULE_MATCH",
        "issues": issues,
        "notice": "التحليل ساكن ولا يشغّل الكود. النتائج تعتمد على القواعد الحالية ولا تثبت خلو البرنامج من الأخطاء."
    }, ensure_ascii=False)
