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

    def test_sequence_repetition_is_valid(self):
        self.assertNotIn("تعارض أنواع البيانات", self.titles('message = "ha" * 3'))

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

    def test_comprehension_target_does_not_leak_to_function(self):
        source = "def build(items):\n    result = [item for item in items]\n    return item"
        self.assertTrue(self.has_name_error(source))

    def test_comprehension_target_is_available_inside_comprehension(self):
        source = "items = [1, 2, 3]\nsquares = [item * item for item in items]"
        self.assertFalse(self.has_name_error(source))

    def test_comprehension_can_read_enclosing_function_local(self):
        source = "def build(items):\n    factor = 2\n    return [item * factor for item in items]"
        self.assertFalse(self.has_name_error(source))

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

    def test_syntax_error_preserved(self):
        self.assertEqual(scan("def broken(:")["status"], "SYNTAX_ERROR")


if __name__ == "__main__":
    unittest.main()
