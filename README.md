# CODE DOCTOR AI — Phase 1

Android starter app with an offline Python source analyzer embedded using Chaquopy.

## Features
- Paste Python code or import a text/Python file.
- Parse source with Python's AST without executing submitted code.
- Detect syntax errors, constant division by zero, eval/exec calls, mutable defaults, broad except, and possible hard-coded secrets.
- Arabic explanations, line numbers, severity and suggested next steps.

## Important limitations
This is an early rule-based analyzer, not a complete AI debugger or malware detector. A clean report means only that current rules found no match; it does not prove code correctness or security. No automatic code rewriting or cloud AI is enabled yet.

## Build
GitHub Actions builds a debug APK on pushes to main or manually from Actions.

## Next
Add broader diagnostics, unit tests and validated fix previews; then optional cloud AI via a protected backend. Never embed API secrets in the APK.
