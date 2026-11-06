# CODE DOCTOR AI — Android Python Analyzer

Code Doctor AI is an offline-first Android tool for reviewing Python source code. It parses source statically and never runs the submitted program.

## Current capabilities

- Paste Python code or import a local Python/text file.
- Detect Python syntax and compile-time scope errors without executing the source.
- Detect common definite errors such as constant division by zero, incompatible literal operations, invalid indexing and invalid `len()` calls.
- Check undefined names with separate module, function, nested-function, class, lambda and comprehension scopes.
- Detect likely local-variable reads before initialization and selected branch-related unbound-local cases.
- Warn about selected risky patterns: direct `eval`/`exec`, `os.system`, `subprocess` with `shell=True`, unsafe `pickle`/`marshal` loading, unsafe `yaml.load`, and likely hard-coded secrets.\n- Run a separate static taint-flow pass that follows simple aliases and branch merges from `input()` / web request parameters into dynamic Python execution, shell commands and SQL query sinks.
- Explain findings in Arabic with line numbers, severity, confidence and suggested corrections.
- Copy source and reports, export a text report, and keep the latest 10 scan records locally on the device.

## Privacy and safety

- Source analysis runs locally through the embedded Python runtime; source code is not uploaded to a server.
- The analyzer parses and compiles source for validation but does not execute the submitted program.
- The analyzer is rule-based. A clean result means only that the current checks found no issue; it is not proof that code is correct, secure, or malware-free.
- Security warnings are indicators for review, not proof of malicious behavior.
- Never put API keys, signing passwords or private credentials in source files or the APK.

## Build and tests

GitHub Actions runs the Python regression suite, compatibility checks, then builds Android APKs. The workflow can be started manually from the Actions page on the selected branch. Release signing requires the repository's existing signing secrets.

## Planned improvements

- Expand taint propagation across helper functions, containers and sanitizers while keeping conservative confidence levels.
- Additional security rules and false-positive regression tests.
- Safe fix previews that show a diff and never rewrite source without user approval.
- Optional AI explanations through a protected backend; no secret API key will be embedded in the Android app.
