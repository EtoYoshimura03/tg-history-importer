"""Smoke test: the wizard module imports cleanly (questionary available)."""

from __future__ import annotations


def test_wizard_imports():
    import tg_history_importer.wizard as wizard

    assert hasattr(wizard, "run_wizard")
