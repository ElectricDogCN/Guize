"""Preserve safe history parsing with optional native acceleration."""
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "history_yaml_loader_regression", ROOT / "scripts/check-program-plan-history.py"
)
HISTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HISTORY)


@pytest.mark.parametrize("path", [
    "specs/coordination/program-plan.yaml",
    "specs/coordination/active-work.yaml",
    "specs/coordination/program-plan.schema.yaml",
])
def test_real_history_documents_keep_safe_yaml_values(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    assert HISTORY.load_yaml_text(text) == yaml.safe_load(text)


@pytest.mark.parametrize("text", [
    "",
    "null\n",
    "flag: true\ncount: 12\nname: 归泽\n",
    "lease: 2026-10-28T05:32:42Z\n",
    "defaults: &defaults {status: reserved, modules: [MOD-GOV]}\n"
    "task: {<<: *defaults, status: in_progress}\n",
])
def test_scalar_timestamp_unicode_and_merge_semantics_are_preserved(text):
    assert HISTORY.load_yaml_text(text) == yaml.safe_load(text)


@pytest.mark.parametrize("text", [
    "broken: [unterminated",
    "value: \x00",
    "!!python/object/apply:builtins.str [untrusted]",
    "!!python/name:builtins.eval ''",
])
def test_malformed_and_unsafe_documents_remain_rejected(text):
    assert HISTORY.load_yaml_text(text) is None


def test_absent_document_remains_absent():
    assert HISTORY.load_yaml_text(None) is None


def test_without_c_extension_safe_loading_and_rejection_still_work(monkeypatch):
    monkeypatch.delattr(yaml, "CSafeLoader", raising=False)
    text = (ROOT / "specs/coordination/program-plan.yaml").read_text(encoding="utf-8")
    assert HISTORY.load_yaml_text(text) == yaml.safe_load(text)
    assert HISTORY.load_yaml_text("!!python/object/apply:builtins.str [untrusted]") is None
    assert HISTORY.load_yaml_text("broken: [unterminated") is None
