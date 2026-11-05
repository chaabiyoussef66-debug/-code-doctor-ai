import json
import unittest
import analyzer


def scan(source):
    return json.loads(analyzer.analyze(source))


class AnalyzerRuntimeErrorTests(unittest.TestCase):
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


    def test_syntax_error_preserved(self):
        self.assertEqual(scan("def broken(:")["status"], "SYNTAX_ERROR")


if __name__ == "__main__":
    unittest.main()
