"""Staging harness support: isolation guards used by the staged test suite.

This subpackage is Phase A test infrastructure, not product code. It exists so
that the guards are importable by name from `tests/conftest.py` and from later
staged test suites without copying guard code between test directories.
"""
