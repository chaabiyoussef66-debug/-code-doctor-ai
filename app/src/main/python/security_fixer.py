"""Conservative Flask security autofix previews. Submitted code is parsed, never executed."""
import ast
import json


def _offsets(source):
    lines = source.splitlines(keepends=True)
    starts = []
    total = 0
    for line in lines:
        starts.append(total)
        total += len(line.encode("utf-8"))
    return lines, starts


def _absolute(starts, node, end=False):
    line = node.end_lineno if end else node.lineno
    col = node.end_col_offset if end else node.col_offset
    return starts[line - 1] + col


def fix_flask_security(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    lines, starts = _offsets(source)
    raw = source.encode("utf-8")
    replacements = []
    changes = []
    password_manual = False

    for node in ast.walk(tree):
        # request.form["field"] -> request.form.get("field", "")
        if (isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "form"
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "request"
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            start, end = _absolute(starts, node), _absolute(starts, node, True)
            original = raw[start:end].decode("utf-8")
            replacement = "request.form.get(" + repr(node.slice.value) + ', "")'
            if original.startswith("request.form["):
                replacements.append((start, end, replacement))
                changes.append({
                    "line": node.lineno,
                    "title": "حماية قراءة حقول Flask",
                    "message": "استبدال الوصول المباشر إلى request.form باستعمال get() مع قيمة افتراضية."
                })

        # app.run(debug=True) -> app.run(debug=False)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (node.func.attr == "run"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "app"):
                for keyword in node.keywords:
                    if keyword.arg == "debug" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        start = _absolute(starts, keyword.value)
                        end = _absolute(starts, keyword.value, True)
                        replacements.append((start, end, "False"))
                        changes.append({
                            "line": keyword.value.lineno,
                            "title": "تعطيل Flask Debug",
                            "message": "تم تغيير debug=True إلى debug=False لتقليل كشف المعلومات."
                        })

        # Password literals are intentionally not rewritten automatically:
        # the correct hash/storage scheme depends on the application's user model.
        if isinstance(node, ast.Compare):
            left = node.left
            comparators = [left] + list(node.comparators)
            for index, comparator in enumerate(comparators[1:]):
                previous = comparators[index]
                if (isinstance(node.ops[index], ast.Eq)
                        and ((isinstance(previous, ast.Name)
                              and previous.id.lower() in {"password", "passwd", "pwd", "user_password"})
                             and isinstance(comparator, ast.Constant)
                             and isinstance(comparator.value, str))):
                    password_manual = True
                if (isinstance(comparator, ast.Name)
                        and comparator.id.lower() in {"password", "passwd", "pwd", "user_password"}
                        and isinstance(previous, ast.Constant)
                        and isinstance(previous.value, str)
                        and isinstance(node.ops[index], ast.Eq)):
                    password_manual = True

    if not changes and not password_manual:
        return None

    fixed = raw
    for start, end, replacement in sorted(replacements, reverse=True):
        fixed = fixed[:start] + replacement.encode("utf-8") + fixed[end:]
    fixed = fixed.decode("utf-8")

    try:
        ast.parse(fixed)
        compile(fixed, "<code-doctor-security-preview>", "exec")
    except (SyntaxError, ValueError, TypeError):
        return json.dumps({
            "can_apply": False, "fixed_code": source, "changes": [],
            "message": "فشل التحقق من المعاينة؛ لم يتغير الكود الأصلي."
        }, ensure_ascii=False)

    if password_manual:
        changes.append({
            "line": 0,
            "title": "كلمة المرور تحتاج إعداداً يدوياً",
            "message": "لم أزل كلمة المرور الثابتة تلقائياً. خزّن تجزئة كلمة المرور خارج الكود (قاعدة بيانات/متغير بيئة) واستعمل werkzeug.security.check_password_hash للتحقق منها."
        })

    if not any(item["line"] > 0 for item in changes):
        return json.dumps({
            "can_apply": False, "fixed_code": source, "changes": changes,
            "message": "لم يُجرَ تعديل آلي. تحذير كلمة المرور يحتاج إعداد تخزين آمن خاص بالتطبيق؛ لم أغيّر الكود."
        }, ensure_ascii=False)

    message = "معاينة إصلاحات Flask الآمنة. راجع الكود قبل التطبيق وأعد الفحص."
    if password_manual:
        message += "\nتنبيه: بقي تحذير كلمة المرور دون تعديل آلي؛ يلزم إعداد التجزئة والتخزين الآمن يدوياً."
    return json.dumps({
        "can_apply": True, "fixed_code": fixed, "changes": changes,
        "message": message
    }, ensure_ascii=False)
