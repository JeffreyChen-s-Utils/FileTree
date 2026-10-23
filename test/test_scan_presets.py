"""Named scan choices retain only valid preferences and require explicit scan activation."""

import dataclasses
import json

from PySide6.QtWidgets import QDialog, QMessageBox
import pytest

from test_gui import window as window  # noqa: PLC0414 - shared fixture
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.gui import i18n
from je_file_tree.gui.scan_preferences import ScanDefaults
from je_file_tree.gui.scan_presets import PRESETS_KEY, ScanPreset, ScanPresetsDialog, read_presets, write_presets
from je_file_tree.gui.scan_worker import analyse


def test_presets_roundtrip_public_choices_and_unicode_without_authority(window, tmp_path):
    options = ScanOptions(include_hidden=False, gentle=True, workers=7, exclude=(".git", "快取"),
                          file_times=True, windows_owners=True, exact_windows_allocation=True, count_hard_links=True)
    preset = ScanPreset("資料 & 照片", str(tmp_path / "照片"), options)
    write_presets(window.settings, (preset,))
    assert read_presets(window.settings) == (preset,)
    stored = json.loads(window.settings.value(PRESETS_KEY))
    flags = stored["presets"][0]["scan"]["options"][0]
    assert "experimental_mft" not in flags and "approval" not in flags


@pytest.mark.parametrize("kind", ["json", "version", "authority", "backend", "workers", "relative", "duplicate"])
def test_corrupt_presets_are_refused_without_overwriting(window, tmp_path, kind):
    preset = ScanPreset("owned", str(tmp_path), ScanOptions())
    write_presets(window.settings, (preset,))
    document = json.loads(window.settings.value(PRESETS_KEY))
    item = document["presets"][0]
    if kind == "version":
        document["version"] = True
    elif kind == "authority":
        item["approval"] = True
    elif kind == "backend":
        item["scan"]["options"][0]["experimental_mft"] = True
    elif kind == "workers":
        item["scan"]["defaults"]["workers"] = True
    elif kind == "relative":
        item["path"] = "relative"
    elif kind == "duplicate":
        document["presets"].append(dict(item, name="OWNED"))
    raw = "{" if kind == "json" else json.dumps(document)
    window.settings.setValue(PRESETS_KEY, raw)
    with pytest.raises(ValueError):
        read_presets(window.settings)
    assert window.settings.value(PRESETS_KEY) == raw


def test_private_backend_cannot_be_saved(window, tmp_path):
    with pytest.raises(ValueError):
        write_presets(window.settings, (ScanPreset("owned", str(tmp_path), ScanOptions(experimental_mft=True)),))
    assert not window.settings.contains(PRESETS_KEY)


def test_dialog_add_update_rename_delete_and_load(window, tmp_path):
    dialog = ScanPresetsDialog(window.settings, str(tmp_path), ScanOptions(workers=7), window)
    try:
        dialog.name.setText("first")
        dialog.add.click()
        assert read_presets(window.settings)[0].options.workers == 7
        dialog.name.setText("renamed")
        dialog.rename.click()
        assert read_presets(window.settings)[0].name == "renamed"
        dialog.path.setText(str(tmp_path / "other"))
        dialog.update.click()
        assert read_presets(window.settings)[0].path == str(tmp_path / "other")
        dialog.load.click()
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert dialog.chosen == read_presets(window.settings)[0]
        dialog.remove.click()
        assert read_presets(window.settings) == ()
        assert not dialog.load.isEnabled()
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize("language", i18n.LANGUAGES)
def test_preset_loading_changes_inputs_without_replacing_results(window, sample_tree, monkeypatch, language):
    i18n.set_language(language)
    window.retranslate()
    outcome = analyse(scan(sample_tree))
    window.results.show_outcome(outcome)
    window.results.select_node(outcome.top_folders[0])
    selected = window.results.selected_node()
    monkeypatch.setattr(window, "start_scan", lambda *_args, **_kwargs: pytest.fail("preset started scanning"))
    defaults = ScanDefaults(2, ())
    window.restore_scan_preferences(ScanOptions(), defaults)
    preset = ScanPreset("saved", str(sample_tree), dataclasses.replace(ScanOptions(), workers=6, exclude=(".git",)))
    window._apply_scan_preset(preset)
    assert window.path_edit.text() == str(sample_tree)
    assert window._scan_options() == preset.options
    assert (defaults.workers, defaults.exclude) == (6, (".git",))
    assert window.results.outcome is outcome and window.results.selected_node() is selected
    assert window._worker is None
    assert window._actions["scan_presets"].text() == i18n.tr("action_scan_presets")


def test_invalid_stored_settings_show_an_error_and_preserve_data(window, monkeypatch):
    warnings = []
    window.settings.setValue(PRESETS_KEY, "invalid")
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(True))
    window.configure_scan_presets()
    assert warnings == [True] and window.settings.value(PRESETS_KEY) == "invalid"


def test_preset_editor_does_not_suspend_source_readers(window, monkeypatch):
    suspended = []
    monkeypatch.setattr(window, "pending_source_workers", lambda: suspended.append(True) or ())

    def execute(dialog):
        assert not window.operation_busy and not suspended
        assert dialog in window._settings_dialogs
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(ScanPresetsDialog, "exec", execute)
    window.configure_scan_presets()
    assert not suspended and not window._settings_dialogs


def test_application_can_close_while_preset_editor_is_open(window, monkeypatch):
    def execute(dialog):
        window.close()
        assert window._close_ready
        assert dialog.result() == QDialog.DialogCode.Rejected
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(ScanPresetsDialog, "exec", execute)
    try:
        window.configure_scan_presets()
        assert not window._settings_dialogs
    finally:
        window._closing = False
