import json
import unittest

from fixer import fix_code


class FlaskSecurityAutofixTests(unittest.TestCase):
    def test_request_form_fields_use_get(self):
        source = 'from flask import request\nname = request.form["name"]\nemail = request.form[\'email\']\n'
        result = json.loads(fix_code(source))
        self.assertTrue(result["can_apply"])
        self.assertIn('request.form.get(\'name\', "")', result["fixed_code"])
        self.assertIn('request.form.get(\'email\', "")', result["fixed_code"])
        compile(result["fixed_code"], "<test>", "exec")

    def test_flask_debug_is_disabled(self):
        source = 'from flask import Flask\napp = Flask(__name__)\napp.run(debug=True)\n'
        result = json.loads(fix_code(source))
        self.assertTrue(result["can_apply"])
        self.assertIn("app.run(debug=False)", result["fixed_code"])

    def test_password_literal_is_never_claimed_as_auto_fixed(self):
        source = 'password = request.form.get("password")\nif password == "hard-coded-secret":\n    print("ok")\n'
        result = json.loads(fix_code(source))
        self.assertFalse(result["can_apply"])
        self.assertEqual(source, result["fixed_code"])
        self.assertIn("check_password_hash", result["message"])

    def test_combined_flask_fixes_keep_password_manual(self):
        source = ('from flask import request\n'
                  'password = request.form["password"]\n'
                  'if password == "hard-coded-secret":\n'
                  '    print("ok")\n'
                  'app.run(debug=True)\n')
        result = json.loads(fix_code(source))
        self.assertTrue(result["can_apply"])
        self.assertIn('request.form.get(\'password\', "")', result["fixed_code"])
        self.assertIn("debug=False", result["fixed_code"])
        self.assertIn("بقي تحذير كلمة المرور", result["message"])
        self.assertNotIn("hard-coded-secret", result["fixed_code"])


if __name__ == "__main__":
    unittest.main()
