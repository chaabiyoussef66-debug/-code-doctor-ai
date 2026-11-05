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

    def test_syntax_error_is_never_rewritten(self):
        source = "def broken(:\n    pass\n"
        result = repair(source)
        self.assertFalse(result["can_apply"])
        self.assertEqual(result["fixed_code"], source)

    def test_does_not_move_across_control_flow(self):
        source = "def calculate(flag):\n    print(total)\n    if flag:\n        pass\n    total = 100\n"
        result = repair(source)
        self.assertFalse(result["can_apply"])
        self.assertEqual(result["fixed_code"], source)


if __name__ == "__main__":
    unittest.main()
