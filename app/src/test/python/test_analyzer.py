import json
import unittest
import analyzer


def scan(source):
    return json.loads(analyzer.analyze(source))


class AnalyzerRuntimeErrorTests(unittest.TestCase):
    def test_analyzer_build_fingerprint_is_returned(self):
        self.assertEqual(scan("value = 1")["analyzer_build_id"], "scope-diagnostic-3")

    def titles(self, source):
        return [item["title"] for item in scan(source)["issues"]]

    def has_name_error(self, source):
        return "اسم أو متغير غير معرّف" in self.titles(source)

    def test_zero_division_constant(self):
        result = scan("value = 10 / 0")
        item = next(x for x in result["issues"] if x["title"] == "قسمة على صفر")
        self.assertEqual(item["confidence"], "CONFIRMED")

    def test_undefined_name(self):
        self.assertTrue(self.has_name_error("print(tax_rate)"))

    def test_user_typo_name_example(self):
        self.assertTrue(self.has_name_error('name = "Youssef"\nprint(nam)'))

    def test_guarded_zero_division_is_not_reported(self):
        source = "x = 0\nif x != 0:\n    result = 10 / x\nelse:\n    result = 0\nprint(result)"
        self.assertNotIn("قسمة على صفر", self.titles(source))

    def test_zero_division_through_variable(self):
        result = scan("a = 10\nb = 0\nresult = a / b\nprint(result)")
        item = next(x for x in result["issues"] if x["title"] == "قسمة على صفر")
        self.assertEqual(item["line"], 3)


    def test_zero_division_from_literal_function_argument(self):
        source = "def calculate(divisor):\n    result = 100 / divisor\n    print(result)\n\ncalculate(0)"
        result = scan(source)
        item = next(x for x in result["issues"] if x["title"] == "قسمة على صفر")
        self.assertEqual(item["line"], 2)
        self.assertEqual(item["confidence"], "CONFIRMED")

    def test_nonzero_function_argument_does_not_report_zero_division(self):
        source = "def calculate(divisor):\n    result = 100 / divisor\n    print(result)\n\ncalculate(5)"
        self.assertNotIn("قسمة على صفر", self.titles(source))

    def test_zero_function_argument_is_safe_when_division_is_guarded(self):
        source = "def calculate(divisor):\n    if divisor != 0:\n        result = 100 / divisor\n        print(result)\n\ncalculate(0)"
        self.assertNotIn("قسمة على صفر", self.titles(source))

    def test_zero_division_from_module_variable_argument(self):
        source = "divisor = 0\ndef calculate(value):\n    result = 100 / value\ncalculate(divisor)"
        result = scan(source)
        item = next(x for x in result["issues"] if x["title"] == "قسمة على صفر")
        self.assertEqual(item["line"], 3)
        self.assertEqual(item["confidence"], "CONFIRMED")

    def test_nonzero_module_variable_argument_is_safe(self):
        source = "divisor = 5\ndef calculate(value):\n    result = 100 / value\ncalculate(divisor)"
        self.assertNotIn("قسمة على صفر", self.titles(source))

    def test_module_variable_alias_is_resolved_for_function_call(self):
        source = "base = 0\ndivisor = base\ndef calculate(value):\n    return 10 / value\ncalculate(divisor)"
        self.assertIn("قسمة على صفر", self.titles(source))

    def test_constant_index_out_of_range(self):
        self.assertIn("فهرس خارج الحدود", self.titles("items = [1, 2]\nprint(items[5])"))

    def test_incompatible_literal_types(self):
        self.assertIn("تعارض أنواع البيانات", self.titles('result = "age: " + 20'))

    def test_valid_simple_code_no_false_runtime_error(self):
        source = "tax_rate = 0.2\ntotal = 100 * tax_rate\nprint(total)"
        self.assertFalse(self.has_name_error(source))

    def test_function_arguments_are_not_undefined(self):
        self.assertFalse(self.has_name_error("def divide(a, b):\n    return a / b"))

    def test_undefined_name_inside_function(self):
        self.assertTrue(self.has_name_error("def calculate():\n    return missing_value"))

    def test_local_read_before_assignment_is_reported(self):
        source = "def calculate():\n    print(value)\n    value = 3"
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_local_assigned_on_both_if_paths_is_safe(self):
        source = "def calculate(flag):\n    if flag:\n        value = 1\n    else:\n        value = 2\n    return value"
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_local_assigned_on_only_one_if_path_is_potentially_unbound(self):
        source = "def calculate(flag):\n    if flag:\n        value = 1\n    return value"
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))


    def test_sequence_repetition_is_valid(self):
        self.assertNotIn("تعارض أنواع البيانات", self.titles('message = "ha" * 3'))

    def test_false_boolean_denominator_is_zero(self):
        self.assertIn("قسمة على صفر", self.titles("result = 1 / False"))

    def test_boolean_arithmetic_is_valid(self):
        self.assertNotIn("تعارض أنواع البيانات", self.titles("result = True + False"))

    def test_bytes_concatenation_is_valid(self):
        self.assertNotIn("تعارض أنواع البيانات", self.titles("result = b'a' + b'b'"))

    def test_string_percent_formatting_is_valid(self):
        self.assertNotIn("تعارض أنواع البيانات", self.titles('result = "hello %s" % "world"'))

    def test_complex_floor_division_is_invalid(self):
        self.assertIn("تعارض أنواع البيانات", self.titles("result = 1j // 1j"))

    def test_len_none_is_invalid(self):
        self.assertIn("نوع غير صالح للدالة len", self.titles("result = len(None)"))

    def test_sequence_string_index_is_invalid(self):
        self.assertIn("نوع فهرس غير صالح", self.titles('items = [1, 2]\nprint(items["first"])'))

    def test_missing_dictionary_key_is_reported(self):
        self.assertIn("مفتاح غير موجود", self.titles('items = {"a": 1}\nprint(items["b"])'))


    def test_local_name_does_not_leak_between_functions(self):
        source = "def first():\n    hidden = 1\ndef second():\n    return hidden"
        self.assertTrue(self.has_name_error(source))

    def test_nested_function_can_read_outer_local(self):
        source = "def outer():\n    value = 3\n    def inner():\n        return value\n    return inner()"
        self.assertFalse(self.has_name_error(source))

    def test_builtin_inside_function_is_not_undefined(self):
        self.assertFalse(self.has_name_error("def show(items):\n    return len(items)"))

    def test_class_body_can_read_earlier_class_binding(self):
        source = "class Sample:\n    value = 4\n    copied = value"
        self.assertFalse(self.has_name_error(source))

    def test_method_does_not_implicitly_close_over_class_namespace(self):
        source = "class Sample:\n    value = 4\n    def method(self):\n        return value"
        self.assertTrue(self.has_name_error(source))

    def test_method_parameter_and_instance_attribute(self):
        source = "class Sample:\n    def method(self, value):\n        return self.value + value"
        self.assertFalse(self.has_name_error(source))

    def test_nested_class_does_not_close_over_outer_class_names(self):
        source = "class Outer:\n    hidden = 1\n    class Inner:\n        def method(self):\n            return hidden"
        self.assertTrue(self.has_name_error(source))

    def test_method_does_not_use_class_constant_as_local_constant(self):
        source = "class Sample:\n    denominator = 0\n    def calculate(self):\n        return 10 / denominator"
        self.assertNotIn("قسمة على صفر", self.titles(source))


    def test_comprehension_target_does_not_leak_to_function(self):
        source = "def build(items):\n    result = [item for item in items]\n    return item"
        self.assertTrue(self.has_name_error(source))

    def test_comprehension_target_does_not_trigger_local_unbound_warning(self):
        source = "def build(items):\n    result = [item for item in items]\n    item = 4\n    return result"
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))


    def test_comprehension_target_is_available_inside_comprehension(self):
        source = "items = [1, 2, 3]\nsquares = [item * item for item in items]"
        self.assertFalse(self.has_name_error(source))

    def test_comprehension_can_read_enclosing_function_local(self):
        source = "def build(items):\n    factor = 2\n    return [item * factor for item in items]"
        self.assertFalse(self.has_name_error(source))
    def test_later_comprehension_target_is_not_visible_in_its_iterable(self):
        source = "items = [1, 2]\nresult = [x for x in items for y in missing_iterable]"
        self.assertTrue(self.has_name_error(source))


    def test_comprehension_does_not_capture_class_local(self):
        source = "class Sample:\n    value = 4\n    result = [value for _ in range(1)]"
        self.assertTrue(self.has_name_error(source))

    def test_global_assignment_is_available_in_function(self):
        source = "def update():\n    global counter\n    counter = 1\n    return counter"
        self.assertFalse(self.has_name_error(source))

    def test_global_read_without_module_binding_is_reported(self):
        source = "def read():\n    global missing\n    return missing"
        self.assertTrue(self.has_name_error(source))

    def test_nonlocal_reads_outer_function_binding(self):
        source = "def outer():\n    value = 1\n    def inner():\n        nonlocal value\n        value = value + 1\n        return value\n    return inner()"
        self.assertFalse(self.has_name_error(source))

    def test_import_inside_function_is_available(self):
        source = "def parse():\n    import json\n    return json.loads('{}')"
        self.assertFalse(self.has_name_error(source))

    def test_function_default_is_checked_in_parent_scope(self):
        source = "def build(value=missing_default):\n    return value"
        self.assertTrue(self.has_name_error(source))


    def test_match_pattern_capture_is_defined_inside_case(self):
        source = 'def get_name(data):\n    match data:\n        case {"name": captured}:\n            return captured'
        self.assertFalse(self.has_name_error(source))
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_match_pattern_capture_is_not_guaranteed_after_match(self):
        source = 'def get_name(data):\n    match data:\n        case {"name": captured}:\n            pass\n    return captured'
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_match_star_capture_is_defined_inside_case(self):
        source = "def first_item(data):\n    match data:\n        case [first, *remaining]:\n            return first"
        self.assertFalse(self.has_name_error(source))


    def test_nonlocal_without_enclosing_binding_is_syntax_error(self):
        source = "def outer():\n    def inner():\n        nonlocal missing\n        return missing"
        self.assertEqual(scan(source)["status"], "SYNTAX_ERROR")

    def test_return_outside_function_is_syntax_error(self):
        self.assertEqual(scan("return 5")["status"], "SYNTAX_ERROR")

    def test_function_constant_does_not_leak_into_another_function(self):
        source = "def first():\n    denominator = 0\n    return 10 / denominator\ndef second(denominator):\n    return 10 / denominator"
        result = scan(source)
        zero_divisions = [x for x in result["issues"] if x["title"] == "قسمة على صفر"]
        self.assertEqual(len(zero_divisions), 1)
        self.assertEqual(zero_divisions[0]["line"], 3)

    def test_method_does_not_inherit_class_constant_for_division(self):
        source = "class Sample:\n    denominator = 0\n    def calculate(self, denominator):\n        return 10 / denominator"
        self.assertNotIn("قسمة على صفر", self.titles(source))

    def test_class_constant_analysis_continues_after_method_definition(self):
        source = "class Sample:\n    denominator = 0\n    def method(self):\n        return 1\n    result = 10 / denominator"
        self.assertIn("قسمة على صفر", self.titles(source))



    def test_unhashable_set_literal_does_not_crash_analyzer(self):
        result = scan("value = {[]}")
        self.assertIn(result["status"], ("NO_RULE_MATCH", "ISSUES_FOUND"))

    def test_direct_eval_is_flagged(self):
        self.assertIn("تنفيذ ديناميكي للكود", self.titles("result = eval(user_input)"))

    def test_unrelated_method_named_eval_is_not_flagged(self):
        self.assertNotIn("تنفيذ ديناميكي للكود", self.titles("result = service.eval()"))

    def test_subprocess_shell_true_is_flagged(self):
        source = "import subprocess\nsubprocess.run(command, shell=True)"
        self.assertIn("subprocess مع shell=True", self.titles(source))

    def test_subprocess_shell_false_is_not_flagged(self):
        source = "import subprocess\nsubprocess.run([command, argument], shell=False)"
        self.assertNotIn("subprocess مع shell=True", self.titles(source))

    def test_pickle_load_is_flagged(self):
        source = "import pickle\npickle.loads(data)"
        self.assertIn("فك تسلسل غير آمن", self.titles(source))

    def test_requests_verify_false_is_flagged(self):
        source = "import requests\nrequests.get(url, verify=False)"
        self.assertIn("تعطيل التحقق من شهادة HTTPS", self.titles(source))

    def test_requests_verify_true_is_not_flagged(self):
        source = "import requests\nrequests.get(url, verify=True)"
        self.assertNotIn("تعطيل التحقق من شهادة HTTPS", self.titles(source))

    def test_weak_hash_is_flagged(self):
        source = "import hashlib\nhashlib.md5(data)"
        self.assertIn("خوارزمية تجزئة ضعيفة", self.titles(source))

    def test_insecure_tempfile_helper_is_flagged(self):
        source = "import tempfile\ntempfile.mktemp()"
        self.assertIn("إنشاء ملف مؤقت بطريقة غير آمنة", self.titles(source))

    def test_sql_fstring_is_flagged(self):
        source = 'cursor.execute(f"SELECT * FROM users WHERE name = {name}")'
        self.assertIn("احتمال حقن SQL عبر f-string", self.titles(source))



    def test_module_read_before_assignment_is_reported(self):
        source = "print(value)\nvalue = 2"
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_module_read_after_assignment_is_safe(self):
        source = "value = 2\nprint(value)"
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_class_read_before_assignment_is_reported(self):
        source = "class Sample:\n    print(value)\n    value = 2"
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_class_read_after_assignment_is_safe(self):
        source = "class Sample:\n    value = 2\n    print(value)"
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_syntax_error_preserved(self):
        self.assertEqual(scan("def broken(:")["status"], "SYNTAX_ERROR")


    def test_hardcoded_password_comparison_is_flagged(self):
        source = 'password = request.form["password"]\nif password == "1234":\n    login()'
        self.assertIn("كلمة مرور ثابتة داخل الكود", self.titles(source))

    def test_flask_debug_true_is_flagged(self):
        source = "from flask import Flask\napp = Flask(__name__)\napp.run(debug=True)"
        self.assertIn("تفعيل Flask Debug", self.titles(source))

    def test_flask_debug_false_is_not_flagged(self):
        source = "app.run(debug=False)"
        self.assertNotIn("تفعيل Flask Debug", self.titles(source))

    def test_direct_request_form_key_access_is_flagged(self):
        source = 'username = request.form["username"]'
        self.assertIn("الوصول إلى حقل نموذج دون تحقق", self.titles(source))

    def test_request_form_get_is_not_flagged_as_direct_access(self):
        source = 'username = request.form.get("username")'
        self.assertNotIn("الوصول إلى حقل نموذج دون تحقق", self.titles(source))


    def test_sql_string_concatenation_is_flagged(self):
        source = 'query = "SELECT * FROM users WHERE name = " + username\ncursor.execute(query)'
        self.assertIn("احتمال حقن SQL عبر تركيب النص", self.titles(source))

    def test_sql_format_is_flagged(self):
        source = 'cursor.execute("SELECT * FROM users WHERE name = {}".format(username))'
        self.assertIn("احتمال حقن SQL عبر تركيب النص", self.titles(source))

    def test_render_template_string_dynamic_template_is_flagged(self):
        source = 'from flask import render_template_string\nrender_template_string("<p>" + user_input + "</p>")'
        self.assertIn("احتمال حقن قالب أو XSS", self.titles(source))

    def test_render_template_string_static_template_is_not_flagged(self):
        source = 'render_template_string("<p>Hello</p>", name=username)'
        self.assertNotIn("احتمال حقن قالب أو XSS", self.titles(source))

    def test_markup_dynamic_content_is_flagged(self):
        self.assertIn("تعطيل تهريب HTML بمحتوى ديناميكي", self.titles("Markup(user_input)"))

    def test_markup_static_content_is_not_flagged(self):
        self.assertNotIn("تعطيل تهريب HTML بمحتوى ديناميكي", self.titles('Markup("<b>safe</b>")'))

    def test_secret_assignment_is_flagged(self):
        self.assertIn("احتمال وجود سر داخل الكود", self.titles('API_KEY = "123456789abcdef"'))

    def test_environment_secret_is_not_flagged(self):
        self.assertNotIn("احتمال وجود سر داخل الكود", self.titles('API_KEY = os.environ.get("API_KEY")'))


    def test_match_irrefutable_fallback_assigns_name_on_all_paths(self):
        source = 'def get_name(data):\n    match data:\n        case {"name": captured}:\n            print(captured)\n        case _:\n            captured = "Unknown"\n    print(captured)'
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_match_with_guarded_wildcard_is_not_exhaustive(self):
        source = 'def get_name(data, flag):\n    match data:\n        case {"name": captured}:\n            pass\n        case _ if flag:\n            captured = "Unknown"\n    print(captured)'
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_exhaustive_match_return_paths_make_following_code_unreachable(self):
        source = 'def get_name(data):\n    match data:\n        case {"name": captured}:\n            return captured\n        case _:\n            return "Unknown"\n    print(captured)'
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_match_with_nonreturning_fallback_keeps_following_code_reachable(self):
        source = 'def get_name(data):\n    match data:\n        case {"name": captured}:\n            return captured\n        case _:\n            pass\n    print(captured)'
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))



    def test_try_handler_return_does_not_hide_continuing_normal_path(self):
        source = "def calculate(flag):\n    try:\n        if flag:\n            result = 100\n            return result\n        else:\n            pass\n    except Exception:\n        return -1\n    print(result)\n\ncalculate(False)"
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_try_all_return_paths_make_following_code_unreachable(self):
        source = "def calculate(flag):\n    try:\n        if flag:\n            result = 100\n            return result\n        else:\n            return 0\n    except Exception:\n        return -1\n    print(result)"
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))


    def test_while_break_paths_assign_local_on_all_exits(self):
        source = "def calculate(flag):\n    while True:\n        if flag:\n            result = 100\n            break\n        else:\n            result = 200\n            break\n    print(result)\n\ncalculate(False)"
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_while_break_path_without_assignment_is_reported(self):
        source = "def calculate(flag):\n    while True:\n        if flag:\n            result = 100\n            break\n        else:\n            break\n    print(result)"
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_while_true_without_break_keeps_following_code_unreachable(self):
        source = "def calculate():\n    while True:\n        continue\n    print(missing_local)"
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_for_break_paths_assign_local_on_all_exits(self):
        source = "def calculate(flag, items):\n    for item in items:\n        if flag:\n            result = 100\n            break\n        else:\n            result = 200\n            break\n    else:\n        result = 300\n    print(result)"
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_for_empty_iterable_path_without_assignment_is_reported(self):
        source = "def calculate(items):\n    for item in items:\n        result = 100\n        break\n    print(result)"
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))


    def test_nested_for_inner_break_assigns_local_before_outer_exit(self):
        source = "def calculate():\n    for i in range(3):\n        for j in range(3):\n            result = 100\n            break\n    print(result)\ncalculate()"
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_nested_for_unknown_outer_iterable_keeps_empty_path(self):
        source = "def calculate(items):\n    for i in items:\n        for j in range(3):\n            result = 100\n            break\n    print(result)"
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))


    def test_for_continue_runs_else_on_normal_exhaustion(self):
        source = """def calculate():
    for item in [1]:
        continue
    else:
        result = 7
    return result"""
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_for_continue_keeps_following_code_reachable_through_else(self):
        source = """def calculate():
    for item in [1]:
        continue
    else:
        result = 7
    print(result)"""
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))


    def test_finally_return_makes_following_undefined_name_unreachable(self):
        source = "def calculate(value):\n    try:\n        if value > 0:\n            return value\n    finally:\n        return 100\n    print(result)\n\ncalculate(5)"
        self.assertFalse(self.has_name_error(source))

    def test_conditional_finally_return_keeps_other_path_reachable(self):
        source = "def calculate(flag):\n    try:\n        pass\n    finally:\n        if flag:\n            return 100\n    print(missing_value)"
        self.assertTrue(self.has_name_error(source))


    def test_break_in_finally_overrides_pending_return(self):
        source = """def calculate(flag):
    while True:
        try:
            return 10
        finally:
            if not flag:
                break
    print(missing_value)

calculate(False)"""
        self.assertTrue(self.has_name_error(source))

    def test_unconditional_raise_routes_to_handler_without_false_unbound_warning(self):
        source = """def calculate():
    try:
        raise ValueError("bad input")
    except ValueError:
        value = 7
    return value"""
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_unconditional_raise_handler_without_assignment_keeps_unbound_warning(self):
        source = """def calculate(flag):
    try:
        raise ValueError("bad input")
    except ValueError:
        if flag:
            value = 7
    return value"""
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_exception_alias_read_after_handler_has_specific_diagnostic(self):
        source = """def calculate():
    try:
        raise ValueError("test")
    except ValueError as error:
        pass
    print(error)"""
        result = scan(source)
        matches = [
            item for item in result["issues"]
            if item["title"] == "استعمال متغير الاستثناء بعد انتهاء except"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["line"], 6)
        self.assertEqual(matches[0]["confidence"], "CONFIRMED")

    def test_reassigned_exception_alias_can_be_read_after_handler(self):
        source = """def calculate():
    try:
        raise ValueError("test")
    except ValueError as error:
        pass
    error = "saved"
    print(error)"""
        self.assertNotIn(
            "استعمال متغير الاستثناء بعد انتهاء except",
            self.titles(source)
        )
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))


    def test_conditional_exception_alias_reassignment_is_not_confirmed_as_cleared(self):
        source = """def test(flag):
    try:
        raise ValueError("original")
    except ValueError as error:
        pass
    if flag:
        error = "saved"
    print(error)"""
        result = scan(source)
        titles = [item["title"] for item in result["issues"]]
        self.assertIn("استعمال متغير محلي قبل التهيئة", titles)
        self.assertNotIn("استعمال متغير الاستثناء بعد انتهاء except", titles)

    def test_different_except_aliases_do_not_leak_between_handlers(self):
        source = """def calculate():
    try:
        risky_call()
    except ValueError as value_error:
        pass
    except TypeError as type_error:
        pass
    print(value_error)
    print(type_error)"""
        result = scan(source)
        confirmed_aliases = [
            item["message"] for item in result["issues"]
            if item["title"] == "استعمال متغير الاستثناء بعد انتهاء except"
            and item["confidence"] == "CONFIRMED"
        ]
        self.assertEqual(confirmed_aliases, [])

    def test_same_except_alias_is_confirmed_when_all_handlers_clear_it(self):
        source = """def calculate():
    try:
        risky_call()
    except ValueError as error:
        pass
    except TypeError as error:
        pass
    print(error)"""
        result = scan(source)
        matches = [
            item for item in result["issues"]
            if item["title"] == "استعمال متغير الاستثناء بعد انتهاء except"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["confidence"], "CONFIRMED")

    def test_exception_alias_remains_confirmed_when_no_branch_reassigns_it(self):
        source = """def test(flag):
    try:
        raise ValueError("original")
    except ValueError as error:
        pass
    if flag:
        print("yes")
    else:
        print("no")
    print(error)"""
        result = scan(source)
        matches = [
            item for item in result["issues"]
            if item["title"] == "استعمال متغير الاستثناء بعد انتهاء except"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["confidence"], "CONFIRMED")

    def test_both_if_branches_reassign_exception_alias_without_warning(self):
        source = """def test(flag):
    try:
        raise ValueError("original")
    except ValueError as error:
        pass
    if flag:
        error = "first"
    else:
        error = "second"
    print(error)"""
        titles = self.titles(source)
        self.assertNotIn("استعمال متغير الاستثناء بعد انتهاء except", titles)
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", titles)



    def test_singleton_inner_loop_prunes_impossible_break_and_runs_else(self):
        source = """def test():
    for item in [1]:
        for number in [1]:
            if number == 2:
                break
        else:
            result = "انتهت الحلقة الداخلية"
    print(result)"""
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_singleton_inner_loop_preserves_possible_break(self):
        source = """def test():
    for item in [1]:
        for number in [1]:
            if number == 1:
                break
        else:
            result = "انتهت الحلقة الداخلية"
    print(result)"""
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_unknown_outer_iterable_keeps_empty_path_with_singleton_inner_loop(self):
        source = """def test(items):
    for item in items:
        for number in [1]:
            if number == 2:
                break
        else:
            result = "انتهت الحلقة الداخلية"
    print(result)"""
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))



class AdvancedTaintFlowTests(unittest.TestCase):
    def titles(self, source):
        return [item["title"] for item in scan(source)["issues"]]

    def taint_titles(self, source):
        return [item["title"] for item in scan(source)["issues"]
                if "مدخلات غير موثوقة تصل" in item["title"]]

    def test_user_input_alias_to_eval_is_reported(self):
        source = """payload = input()
eval(payload)"""
        self.assertIn("مدخلات غير موثوقة تصل إلى تنفيذ Python ديناميكي",
                      self.taint_titles(source))

    def test_request_parameter_alias_to_exec_is_reported(self):
        source = """payload = request.args.get("code")
exec(payload)"""
        self.assertIn("مدخلات غير موثوقة تصل إلى تنفيذ Python ديناميكي",
                      self.taint_titles(source))

    def test_user_input_in_sql_query_is_reported(self):
        source = """user_id = request.args.get("id")
query = "SELECT * FROM users WHERE id = " + user_id
cursor.execute(query)"""
        self.assertIn("مدخلات غير موثوقة تصل إلى استعلام SQL",
                      self.taint_titles(source))

    def test_user_input_in_shell_command_is_reported(self):
        source = """host = input()
subprocess.run("ping " + host, shell=True)"""
        self.assertIn("مدخلات غير موثوقة تصل إلى subprocess مع shell=True",
                      self.taint_titles(source))

    def test_constant_eval_argument_is_not_taint_flow(self):
        self.assertNotIn("مدخلات غير موثوقة تصل إلى تنفيذ Python ديناميكي",
                         self.taint_titles("eval('1 + 1')"))

    def test_overwriting_alias_with_constant_clears_taint(self):
        source = """payload = input()
payload = "safe"
eval(payload)"""
        self.assertNotIn("مدخلات غير موثوقة تصل إلى تنفيذ Python ديناميكي",
                         self.taint_titles(source))

    def test_tainted_value_on_one_branch_is_preserved(self):
        source = """if flag:
    payload = input()
else:
    payload = "safe"
eval(payload)"""
        self.assertIn("مدخلات غير موثوقة تصل إلى تنفيذ Python ديناميكي",
                      self.taint_titles(source))

    def test_taint_does_not_leak_between_functions(self):
        source = """def first():
    payload = input()
def second():
    eval("1 + 1")"""
        self.assertEqual(self.taint_titles(source), [])

    def test_os_system_with_user_input_is_reported(self):
        source = """command = input()
os.system(command)"""
        self.assertIn("مدخلات غير موثوقة تصل إلى أمر نظام",
                      self.taint_titles(source))



    def test_try_with_guaranteed_invalid_builtin_int_does_not_report_saved_error(self):
        source = """def calculate():
    try:
        int("invalid")
    except ValueError as error:
        saved_error = str(error)
    return saved_error"""
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_try_with_valid_builtin_int_keeps_normal_path_warning(self):
        source = """def calculate():
    try:
        int("123")
    except ValueError as error:
        saved_error = str(error)
    return saved_error"""
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_shadowed_local_int_does_not_count_as_guaranteed_builtin_error(self):
        source = """def calculate():
    int = lambda value: value
    try:
        int("invalid")
    except ValueError:
        saved_error = "caught"
    return saved_error"""
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_shadowed_module_int_does_not_count_as_guaranteed_builtin_error(self):
        source = """int = lambda value: value

def calculate():
    try:
        int("invalid")
    except ValueError:
        saved_error = "caught"
    return saved_error"""
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))


    def test_non_raising_try_body_does_not_create_unreachable_handler_path(self):
        source = """def calculate():
    try:
        value = 10
    except ValueError:
        pass
    return value"""
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_potentially_raising_call_keeps_handler_path_in_analysis(self):
        source = """def calculate():
    try:
        risky_call()
        value = 10
    except ValueError:
        pass
    return value"""
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))


    def test_multiple_except_handlers_assign_same_local_on_every_path(self):
        source = """def calculate():
    try:
        risky_call()
        value = 1
    except ValueError:
        value = 2
    except TypeError:
        value = 3
    return value"""
        titles = self.titles(source)
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", titles)

    def test_one_except_handler_without_assignment_preserves_unbound_warning(self):
        source = """def calculate():
    try:
        risky_call()
        value = 1
    except ValueError:
        value = 2
    except TypeError:
        pass
    return value"""
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_try_else_and_all_handlers_assign_local(self):
        source = """def calculate():
    try:
        risky_call()
        value = 1
    except ValueError:
        value = 2
    except TypeError:
        value = 3
    else:
        value = 4
    return value"""
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_finally_assignment_initializes_local_after_try_paths(self):
        source = """def calculate():
    try:
        risky_call()
    except ValueError:
        pass
    finally:
        value = 9
    return value"""
        self.assertNotIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

    def test_non_raising_try_with_except_assignment_does_not_assume_handler_runs(self):
        source = """def calculate():
    try:
        pass
    except ValueError:
        value = 9
    return value"""
        self.assertIn("استعمال متغير محلي قبل التهيئة", self.titles(source))

if __name__ == "__main__":
    unittest.main()
