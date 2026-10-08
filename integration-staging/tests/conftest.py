"""Explicit staging test configuration for the Phase A harness.

Not copied from the original tree: the original `conftest.py` is never reused.
This file, in order:

1. creates the private runtime directories and pins HOME/USERPROFILE/TEMP/TMP
   and the application data-root variables into the staging tree;
2. installs the module guard (blocks the original `examdata` package, which the
   shared venv would otherwise resolve through its editable `.pth`);
3. installs the loopback-only network guard;
4. audits after every test that no application module resolves outside staging.

Only staged tests run under this configuration; the original test suite is
never collected or executed.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

STAGING = Path(__file__).resolve().parents[1]

_PRIVATE_DIRS = (
    "runtime/tmp",
    "runtime/home",
    "runtime/data/ielts",
    "runtime/data/toefl",
    "runtime/data/timetable/zone5/pdf",
    "runtime/data/timetable/zone5/matrix",
    "runtime/data/timetable/edexcel/pdf",
    "runtime/data/timetable/edexcel/manifest",
)
for _rel in _PRIVATE_DIRS:
    (STAGING / _rel).mkdir(parents=True, exist_ok=True)

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["HOME"] = str(STAGING / "runtime" / "home")
os.environ["USERPROFILE"] = os.environ["HOME"]
os.environ["TEMP"] = str(STAGING / "runtime" / "tmp")
os.environ["TMP"] = os.environ["TEMP"]
# Explicit product deployment root (R04): product code resolves its root from
# this, not from a directory-name heuristic or __file__ parents.
os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(STAGING)
os.environ["EXAMDATA_IELTS_DIR"] = str(STAGING / "runtime" / "data" / "ielts")
os.environ["EXAMDATA_TOEFL_DIR"] = str(STAGING / "runtime" / "data" / "toefl")
os.environ["EXAMDATA_ZONE5_PDF_DIR"] = str(STAGING / "runtime" / "data" / "timetable" / "zone5" / "pdf")
os.environ["EXAMDATA_ZONE5_MATRIX"] = str(STAGING / "runtime" / "data" / "timetable" / "zone5" / "matrix")
os.environ["EXAMDATA_EDEXCEL_PDF_DIR"] = str(STAGING / "runtime" / "data" / "timetable" / "edexcel" / "pdf")
os.environ["EXAMDATA_EDEXCEL_MANIFEST"] = str(STAGING / "runtime" / "data" / "timetable" / "edexcel" / "manifest")

from examdata_integration.testing import guards  # noqa: E402

guards.install_module_guard()


def pytest_configure(config):
    guards.install_network_guard()


@pytest.fixture(autouse=True)
def _audit_application_modules_after_each_test():
    yield
    guards.assert_app_modules_within_staging()


def pytest_sessionfinish(session, exitstatus):
    guards.assert_app_modules_within_staging()
