import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "python"))
import analyzer

def check(src):
    return json.loads(analyzer.analyze(src))

def test_syntax():
    assert check("def broken(:\n pass")["status"] == "SYNTAX_ERROR"

def test_division():
    assert any(x["title"] == "قسمة على صفر" for x in check("x = 4 / 0")["issues"])

def test_guarded_zero_division():
    src = "x = 0\nif x != 0:\n    result = 10 / x\nelse:\n    result = 0\nprint(result)"
    assert not any(x["title"] == "قسمة على صفر" for x in check(src)["issues"])

def test_eval():
    assert any(x["title"] == "تنفيذ ديناميكي للكود" for x in check("x = eval(data)")["issues"])

def test_mutable_default():
    assert any(x["title"] == "قيمة افتراضية قابلة للتغيير" for x in check("def f(x=[]):\n return x")["issues"])

def test_clean_not_certified():
    result = check("def add(a,b):\n return a+b")
    assert result["status"] == "NO_RULE_MATCH" and result["issues"] == []

if __name__ == "__main__":
    for fn in (test_syntax, test_division, test_eval, test_mutable_default, test_clean_not_certified):
        fn()
        print("PASS", fn.__name__)
