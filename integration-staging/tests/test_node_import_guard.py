"""Node import-resolution guard tests (plan section 11/A02 additional checks).

Copied Node code must not import anything that escapes staging. There is no
copied Node code yet (that arrives with the A06 runner), so these tests use
synthetic JavaScript written under the private staging runtime.
"""
from __future__ import annotations

import pytest

from examdata_integration.testing import guards
from examdata_integration.testing.node_guard import check_node_file, iter_specifiers


def test_relative_import_inside_staging_is_allowed(tmp_path):
    (tmp_path / "ok.mjs").write_text("export const x = 1;\n", encoding="utf-8")
    main = tmp_path / "main.mjs"
    main.write_text("import { x } from './ok.mjs';\n", encoding="utf-8")
    assert check_node_file(main) == ["./ok.mjs"]


def test_relative_import_escaping_staging_is_rejected(tmp_path):
    main = tmp_path / "escape.mjs"
    main.write_text("import x from '../../../../../examdata/src/examdata/api/app.py';\n",
                    encoding="utf-8")
    with pytest.raises(guards.ForbiddenPathError):
        check_node_file(main)


def test_absolute_import_into_original_tree_is_rejected(tmp_path):
    target = guards.WORKSPACE_ROOT / "examdata" / "src" / "examdata" / "api" / "app.py"
    main = tmp_path / "abs.mjs"
    main.write_text(f"require('{target.as_posix()}');\n", encoding="utf-8")
    with pytest.raises(guards.ForbiddenPathError):
        check_node_file(main)


def test_node_file_outside_staging_is_rejected():
    with pytest.raises(guards.ForbiddenPathError):
        check_node_file(guards.WORKSPACE_ROOT / "frontend" / "app.js")


def test_bare_specifiers_are_listed_but_not_resolved():
    text = "import fs from 'node:fs';\nconst x = require('lodash');\n"
    assert list(iter_specifiers(text)) == ["node:fs", "lodash"]
