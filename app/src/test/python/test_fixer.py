import json
import unittest
import fixer


def repair(source):
    return json.loads(fixer.fix_code(source))


class ConservativeFixerTests(unittest.TestCase):
    def test_moves_simple_constant_assignment_before_read(self):
        source = "def calculate():\n    print(total)\n    total = 100\n\ncalculate()\n"
        result = repair(source)
        self.assertTrue(result["can_apply"])
        self.assertEqual(
            result["fixed_code"],
            "def calculate():\n    total = 100\n    print(total)\n\ncalculate()\n"
        )
        compile(result["fixed_code"], "<fixed>", "exec")

    def test_does_not_change_valid_code(self):
        source = "def calculate():\n    total = 100\n    print(total)\n"
        result = repair(source)
        self.assertFalse(result["can_apply"])
        self.assertEqual(result["fixed_code"], source)

    def test_does_not_reorder_conditional_assignment(self):
        source = "def calculate(flag):\n    if flag:\n        total = 100\n    print(total)\n"
        result = repair(source)
        self.assertFalse(result["can_apply"])
        self.assertEqual(result["fixed_code"], source)

    def test_does_not_guess_a_value_for_unbound_variable(self):
        source = "def calculate():\n    print(total)\n"
        result = repair(source)
        self.assertFalse(result["can_apply"])
        self.assertEqual(result["fixed_code"], source)

    def test_does_not_reorder_a_function_parameter(self):
        source = "def calculate(total):\n    print(total)\n    total = 100\n"
        result = repair(source)
        self.assertFalse(result["can_apply"])
        self.assertEqual(result["fixed_code"], source)

    def test_does_not_reorder_a_global_name(self):
        source = "def calculate():\n    global total\n    print(total)\n    total = 100\n"
        result = repair(source)
        self.assertFalse(result["can_apply"])
        self.assertEqual(result["fixed_code"], source)

    def test_syntax_error_is_never_rewritten(self):
        source = "def broken(:\n    pass\n"
        result = repair(source)
        self.assertFalse(result["can_apply"])
        self.assertEqual(result["fixed_code"], source)


    def test_suggests_clear_local_name_typo(self):
        source = "def calculate():\\n    total = 100\\n    print(totla)\\n"
        result = repair(source)
        self.assertTrue(result["can_apply"])
        self.assertIn("print(total)", result["fixed_code"])
        self.assertNotIn("print(totla)", result["fixed_code"])
        compile(result["fixed_code"], "<fixed>", "exec")

    def test_suggests_clear_builtin_typo(self):
        source = "def show():\\n    pritn('hello')\\n"
        result = repair(source)
        self.assertTrue(result["can_apply"])
        self.assertIn("print('hello')", result["fixed_code"])

    def test_does_not_guess_when_no_similar_name_exists(self):
        source = "def show():\\n    print(missing_value)\\n"
        result = repair(source)
        self.assertFalse(result["can_apply"])
        self.assertEqual(result["fixed_code"], source)

    def test_does_not_change_valid_builtin(self):
        source = "def show():\\n    print('hello')\\n"
        result = repair(source)
        self.assertFalse(result["can_apply"])
        self.assertEqual(result["fixed_code"], source)

    def test_ambiguous_typo_is_not_changed(self):
        source = "def show():\\n    total = 1\\n    tatal = 2\\n    print(tota)\\n"
        result = repair(source)
        self.assertFalse(result["can_apply"])
        self.assertEqual(result["fixed_code"], source)

    def test_typo_fix_is_preview_only_and_does_not_execute(self):
        source = "def show():\\n    total = 1\\n    print(totla)\\n"
        result = repair(source)
        self.assertTrue(result["can_apply"])
        self.assertIn("totla", source)
        self.assertIn("total", result["fixed_code"])

    def test_does_not_move_across_control_flow(self):
        source = "def calculate(flag):\n    print(total)\n    if flag:\n        pass\n    total = 100\n"
        result = repair(source)
        self.assertFalse(result["can_apply"])
        self.assertEqual(result["fixed_code"], source)


if __name__ == "__main__":
    unittest.main()
