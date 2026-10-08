"""Shared helpers for the A06 runtime/runner tests (staging harness support).

Not product code: this module only builds fixtures and manifests *inside the
staging tree* for the A06 tests. It never reads the original tree, and the
manifest documents it writes live under the staging runtime scratch directory
(or a pytest tmp path, which the harness also pins inside staging).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from .guards import STAGING_ROOT

STAGING = Path(STAGING_ROOT)
COMPONENTS_DIR = STAGING / "components"
MANIFEST_PATH = COMPONENTS_DIR / "manifest.json"
FAKE_COMPONENT_DIR = COMPONENTS_DIR / "fake-node-cli"
SCRATCH = STAGING / "runtime" / "tmp"

MANIFEST_VERSION = "examdata.component-manifest/1"

#: The secret the fake CLI writes to stderr (see components/fake-node-cli).
FAKE_SECRET = "SUPERSECRET"


def node_executable() -> str | None:
    return shutil.which("node")


def component_spec(**overrides: Any) -> dict[str, Any]:
    """A copy of the staged fake_cli component declaration, with overrides."""
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    spec = dict(payload["components"][0])
    spec.update(overrides)
    return spec


def write_manifest(base_dir: Path, components: list[dict[str, Any]], *,
                   name: str = "manifest.json",
                   manifest_version: str = MANIFEST_VERSION) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / name
    path.write_text(json.dumps({
        "manifest_version": manifest_version,
        "components": components,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def copy_fake_component(dest_parent: Path, name: str = "fake node cli") -> Path:
    """Copy the staged fake component to a caller-chosen directory name."""
    dest_parent.mkdir(parents=True, exist_ok=True)
    dest = dest_parent / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(FAKE_COMPONENT_DIR, dest)
    return dest


def relative_to_staging(path: Path) -> str:
    return path.resolve().relative_to(STAGING).as_posix()


def limits(**overrides: Any):
    from ..runtime.runner import RunnerLimits
    return RunnerLimits(**overrides)


def runner(manifest_set, *, runtime: str | None = None, **kwargs):
    """A NodeRunner with the fake CLI's secret registered for redaction."""
    from ..runtime.runner import NodeRunner
    kwargs.setdefault("secrets", (FAKE_SECRET,))
    return NodeRunner(manifest_set, runtime=runtime, **kwargs)


def env_with(values: Mapping[str, str]) -> dict[str, str]:
    """A minimal environment mapping for resolve_config(env=...) tests."""
    return dict(values)


__all__ = [
    "STAGING", "COMPONENTS_DIR", "MANIFEST_PATH", "FAKE_COMPONENT_DIR", "SCRATCH",
    "MANIFEST_VERSION", "FAKE_SECRET", "node_executable", "component_spec",
    "write_manifest", "copy_fake_component", "relative_to_staging", "limits",
    "runner", "env_with",
]
