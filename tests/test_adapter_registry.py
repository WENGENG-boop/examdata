from types import SimpleNamespace
import pytest
from examdata.adapters import registry


def test_failed_plugin_registration_rolls_back_and_reports(monkeypatch, caplog):
    original = dict(registry._REGISTRY)
    monkeypatch.setattr(registry, "_REGISTRY", dict(original))
    monkeypatch.setattr(registry.pkgutil, "iter_modules", lambda path: [SimpleNamespace(name="broken", ispkg=True)])
    def load(name):
        if name == "examdata.adapters":
            return SimpleNamespace(__path__=[])
        registry.register(type("Partial", (), {"key": "partial"}))
        raise RuntimeError("synthetic import failure")
    monkeypatch.setattr(registry.importlib, "import_module", load)
    failures = registry._load_builtin()
    assert registry._REGISTRY == original
    assert failures == ["broken: RuntimeError: synthetic import failure"]
    assert "synthetic import failure" in caplog.text
    monkeypatch.setattr(registry, "LOAD_FAILURES", failures)
    with pytest.raises(KeyError, match="broken"):
        registry.get_adapter_class("partial")
