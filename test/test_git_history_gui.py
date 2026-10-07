"""Git object display remains read-only and owns every cancellable worker."""

import time

from PySide6.QtCore import Qt

from test_git_history import repository as repository  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.git_history import GitHistory, GitObject
from je_file_tree.gui.git_history import GitHistoryDialog, GitObjectsModel
from je_file_tree.gui.i18n import tr


def _wait(app, ready):
    deadline = time.monotonic() + 15
    while not ready():
        assert time.monotonic() < deadline
        app.processEvents()
        time.sleep(.005)
    app.processEvents()


def test_model_reports_uncompressed_sizes_without_file_operations(qapp):
    model = GitObjectsModel()
    model.set_rows([GitObject("a" * 40, "blob", 1024)])
    assert model.index(0, 2).data() == "1.0 KB"
    assert "blob" in model.index(0, 1).data()
    assert not model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable


def test_native_git_worker_and_gc_advice(qapp, repository):
    root, old_blob, _ = repository
    dialog = GitHistoryDialog(str(root), "auto")
    try:
        _wait(qapp, lambda: not dialog.worker.isRunning())
        assert dialog.model.rows()[0].oid == old_blob
        assert "will not be removed" in dialog.advice.text()
        assert not dialog.stop_button.isEnabled()
    finally:
        dialog.reject()
        dialog.deleteLater()


def test_stop_and_closed_dialog_ignore_queued_inventory(qapp, repository):
    dialog = GitHistoryDialog(str(repository[0]), "auto")
    dialog.stop()
    _wait(qapp, lambda: not dialog.worker.isRunning())
    assert dialog.model.rowCount() == 0 and dialog.status.text() == tr("scan_cancelled")
    dialog.reject()
    dialog._show(GitHistory([GitObject("a" * 40, "blob", 1024)], 1, 1024, 0))
    assert dialog.model.rowCount() == 0
    dialog.deleteLater()
