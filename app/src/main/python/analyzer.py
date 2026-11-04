"""Offline Python analyzer. Submitted source is parsed, never executed."""
import ast
import json
import re

SECRET = re.compile(r"""(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*['"][^'"]{8,}['"]""")

class Inspector(ast.NodeVisitor):
    def __init__(self):
        self.issues = []

    def add(self, severity, title, node, message, suggestion):
        self.issues.append({
            "severity": severity, "title": title,
            "line": getattr(node, "lineno", 1),
            "message": message, "suggestion": suggestion
        })

    def visit_BinOp(self, node):
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self.add("CRITICAL", "قسمة على صفر", node,
                    "المقام ثابت ويساوي صفراً وقد يسبب ZeroDivisionError.",
                    "تحقق من المقام قبل تنفيذ العملية.")
        self.generic_visit(node)

    def visit_Call(self, node):
        name = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else None)
        warnings = {
            "eval": ("استعمال eval", "قد ينفذ تعبيراً غير موثوق.", "تجنب eval واستعمل parsing آمناً."),
            "exec": ("استعمال exec", "قد ينفذ نصاً كتعليمات Python.", "تجنب exec ولا تمرر إليه مدخلات غير موثوقة."),
            "system": ("استدعاء system", "أوامر النظام تحتاج مراجعة المدخلات.", "تجنب shell مع نصوص غير موثوقة."),
            "loads": ("فك تسلسل بيانات", "بعض دوال loads مثل pickle قد تكون خطيرة مع بيانات غير موثوقة.", "استعمل تنسيقاً آمناً مثل JSON عند الإمكان.")
        }
        if name in warnings:
            title, msg, fix = warnings[name]
            self.add("WARNING", title, node, msg, fix)
        if (isinstance(node.func, ast.Attribute) and node.func.attr == "load"
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "yaml"):
            safe = any(k.arg == "Loader" and isinstance(k.value, ast.Attribute)
                       and k.value.attr == "SafeLoader" for k in node.keywords)
            if not safe:
                self.add("WARNING", "yaml.load يحتاج Loader آمن", node,
                    "yaml.load دون SafeLoader قد يكون خطيراً مع بيانات غير موثوقة.",
                    "استعمل yaml.safe_load للبيانات غير الموثوقة.")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if node.type is None:
            self.add("INFO", "except عام", node,
                "التقاط جميع الاستثناءات قد يخفي أخطاء غير متوقعة.",
                "حدد أنواع الاستثناءات المتوقعة وسجل الخطأ عند الحاجة.")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.add("WARNING", "قيمة افتراضية قابلة للتغيير", default,
                    "القيمة الافتراضية تُعاد مشاركتها بين استدعاءات الدالة.",
                    "استعمل None وأنشئ القائمة أو القاموس داخل الدالة.")
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

def analyze(source):
    issues = []
    for number, line in enumerate(source.splitlines(), 1):
        if SECRET.search(line):
            issues.append({
                "severity": "WARNING",
                "title": "احتمال وجود سر داخل الكود",
                "line": number,
                "message": "السطر يشبه تعيين كلمة مرور أو مفتاح أو رمز سري.",
                "suggestion": "لا تضع الأسرار داخل الكود؛ استعمل تخزيناً آمناً."
            })
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        issues.append({
            "severity": "ERROR", "title": "خطأ في صياغة Python",
            "line": exc.lineno or 1, "message": exc.msg or "تعذر تحليل الكود.",
            "suggestion": "راجع الأقواس والنقطتين والمسافات قرب السطر المحدد."
        })
        return json.dumps({"status": "SYNTAX_ERROR", "issues": issues}, ensure_ascii=False)

    inspector = Inspector()
    inspector.visit(tree)
    issues.extend(inspector.issues)
    order = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}
    issues.sort(key=lambda x: (order.get(x["severity"], 9), x["line"]))
    return json.dumps({
        "status": "ISSUES_FOUND" if issues else "NO_RULE_MATCH",
        "issues": issues
    }, ensure_ascii=False)
