"""Policy previews are read-only, cancellable and required again after any edit."""

import threading

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from conftest import make_tree
from test_cleanup import age_tree
from test_gui import _wait
from je_file_tree.core.cleanup_policy import CleanupPolicy, RuleSetting, load_policy
from je_file_tree.core.scanner import scan
from je_file_tree.gui.app import create_window
from je_file_tree.gui.cleanup_policy_dialog import CleanupPolicyDialog
from je_file_tree.gui.main_window import CLEANUP_POLICY_KEY


def test_preview_requires_new_validation_after_every_edit(qapp, tmp_path) -> None:
    make_tree(tmp_path, {"AppData": {"Local": {"Temp": {"file.tmp": b"data"}}}})
    age_tree(tmp_path)
    root = scan(tmp_path).root
    dialog = CleanupPolicyDialog(CleanupPolicy(), root, "B")
    save = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
    try:
        assert not save.isEnabled()
        dialog._controls["temp"][0].setChecked(False)
        dialog.preview()
        old_worker = dialog._current
        _wait(qapp, save.isEnabled)
        assert "removes 1 candidates (4 B)" in dialog.preview_status.text()
        assert root.size == 4 and (tmp_path / "AppData/Local/Temp/file.tmp").is_file()
        dialog._controls["temp"][0].setChecked(True)
        assert not save.isEnabled()
        dialog._shown(old_worker, CleanupPolicy(), (0, 0, 0, 0, True))
        assert not save.isEnabled(), "replaced replies cannot authorize saving"
        dialog.exclusions.setPlainText("relative/path")
        dialog.preview()
        assert not save.isEnabled() and "Invalid policy" in dialog.preview_status.text()
        dialog.exclusions.clear()
        dialog.preview()
        _wait(qapp, save.isEnabled)
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.shutdown()
        dialog.deleteLater()


def test_policy_persists_separately_from_scan_exclusions_and_corruption_disables_rules(qapp, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "en")
    settings.setValue("exclusions", ["do-not-scan"])
    policy = CleanupPolicy((RuleSetting("temp", False, 70),), (str(tmp_path / "keep"),))
    settings.setValue(CLEANUP_POLICY_KEY, policy.dumps())
    window = create_window(settings)
    try:
        assert window._cleanup_policy == policy
        assert window.exclusions() == ["do-not-scan"]
        assert window._scan_options().exclude == ("do-not-scan",)
        assert window.results.cleanup._policy == policy
    finally:
        window.close()
        window.deleteLater()
    settings.setValue(CLEANUP_POLICY_KEY, "damaged")
    window = create_window(settings)
    try:
        assert all(not setting.enabled for setting in window._cleanup_policy.overrides)
        assert "Suggestions are disabled" in window.statusBar().currentMessage()
        assert window.exclusions() == ["do-not-scan"]
    finally:
        window.close()
        window.deleteLater()


def test_edit_dialog_saves_only_reviewed_policy(qapp, tmp_path, monkeypatch) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "en")
    window = create_window(settings)

    def edit(dialog):
        dialog._controls["temp"][0].setChecked(False)
        dialog.preview()
        assert "No completed scan" in dialog.preview_status.text()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(CleanupPolicyDialog, "exec", edit)
    try:
        window.edit_cleanup_policy()
        saved = load_policy(settings.value(CLEANUP_POLICY_KEY))
        assert not saved.setting("temp").enabled
        assert window.results.cleanup._policy == saved
    finally:
        window.close()
        window.deleteLater()


def test_cancelled_preview_never_emits_and_shutdown_joins(qapp, tmp_path, monkeypatch) -> None:
    from je_file_tree.gui import cleanup_policy_dialog as module

    root = scan(tmp_path).root
    entered, release = threading.Event(), threading.Event()
    original = module.find_cleanup

    def delayed(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "find_cleanup", delayed)
    dialog = CleanupPolicyDialog(CleanupPolicy(), root, "B")
    try:
        dialog.preview()
        _wait(qapp, entered.is_set)
        worker = dialog._current
        replies = []
        worker.ready.connect(replies.append)
        dialog._controls["temp"][1].setValue(60)
        release.set()
        dialog.shutdown()
        qapp.processEvents()
        assert not worker.isRunning() and replies == []
        assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
    finally:
        release.set()
        dialog.shutdown()
        dialog.deleteLater()
