import json
import unittest
import analyzer

def scan(source):
    return json.loads(analyzer.analyze(source))

class AnalyzerRuntimeErrorTests(unittest.TestCase):
    def titles(self, source):
        return [item["title"] for item in scan(source)["issues"]]

    def test_zero_division_constant(self):
        result = scan("value = 10 / 0")
        self.assertIn("قسمة على صفر", self.titles("value = 10 / 0"))
        item = next(x for x in result["issues"] if x["title"] == "قسمة على صفر")
        self.assertEqual(item["confidence"], "CONFIRMED")

    def test_undefined_name(self):
        self.assertIn("اسم أو متغير غير معرّف", self.titles("print(tax_rate)"))

    def test_user_typo_name_example(self):
        result = scan('name = "Youssef"\\nprint(nam)')
        self.assertIn("اسم أو متغير غير معرّف", [x["title"] for x in result["issues"]])

    def test_zero_division_through_variable(self):
        result = scan("a = 10\\nb = 0\\nresult = a / b\\nprint(result)")
        item = next(x for x in result["issues"] if x["title"] == "قسمة على صفر")
        self.assertEqual(item["line"], 3)

    def test_constant_index_out_of_range(self):
        self.assertIn("فهرس خارج الحدود", self.titles("items = [1, 2]\nprint(items[5])"))

    def test_incompatible_literal_types(self):
        self.assertIn("تعارض أنواع البيانات", self.titles('result = "age: " + 20'))

    def test_valid_simple_code_no_false_runtime_error(self):
        result = scan("tax_rate = 0.2\ntotal = 100 * tax_rate\nprint(total)")
        self.assertNotIn("اسم أو متغير غير معرّف", self.titles("tax_rate = 0.2\ntotal = 100 * tax_rate\nprint(total)"))

    def test_function_arguments_are_not_undefined(self):
        titles = self.titles("def divide(a, b):\n    return a / b")
        self.assertNotIn("اسم أو متغير غير معرّف", titles)

    def test_undefined_name_inside_function(self):
        titles = self.titles("def calculate():\n    return missing_value")
        self.assertIn("اسم أو متغير غير معرّف", titles)

    def test_sequence_repetition_is_valid(self):
        titles = self.titles('message = "ha" * 3')
        self.assertNotIn("تعارض أنواع البيانات", titles)

    def test_syntax_error_preserved(self):
        self.assertEqual(scan("def broken(:")["status"], "SYNTAX_ERROR")

if __name__ == "__main__":
    unittest.main()
