"""Project rows remain read-only and route explicit review through the existing central handler."""

from PySide6.QtCore import Qt

from test_projects import project_tree as project_tree  # noqa: PLC0414 - explicit fixture re-export
from test_gui import _scanned, _wait, window as window  # noqa: PLC0414 - explicit fixture re-export
from je_file_tree.core.cleanup_policy import CleanupPolicy
from je_file_tree.core.projects import projects
from je_file_tree.gui import main_window as main_module
from je_file_tree.gui.projects import ProjectsDialog, ProjectsModel


def test_model_breakdown_and_explicit_review(qapp, project_tree):
    dialog = ProjectsDialog(project_tree, "auto", CleanupPolicy())
    requested = []
    dialog.review_requested.connect(requested.append)
    try:
        _wait(qapp, lambda: not dialog.worker.isRunning())
        index = next(index for index in range(dialog.model.rowCount())
                     if dialog.model.row_at(index).node.name == "專案")
        selected = dialog.proxy.mapFromSource(dialog.model.index(index, 0))
        dialog.view.setCurrentIndex(selected)
        assert dialog.review.isEnabled()
        assert not dialog.model.flags(dialog.model.index(index, 0)) & Qt.ItemFlag.ItemIsEditable
        expected = list(dialog.model.row_at(index).reviewable.nodes)
        dialog.review_generated()
        assert requested == [expected] and not dialog.worker.isRunning()
    finally:
        dialog.reject()
        dialog.deleteLater()


def test_stop_and_close_ignore_queued_inventory(qapp, project_tree):
    dialog = ProjectsDialog(project_tree, "auto", CleanupPolicy())
    dialog.stop()
    _wait(qapp, lambda: not dialog.worker.isRunning())
    dialog._show(projects(project_tree))
    assert not dialog.model.rows() and not dialog.review.isEnabled()
    dialog.reject()
    dialog._show(projects(project_tree))
    assert not dialog.model.rows()
    dialog.deleteLater()


def test_main_window_supplies_policy_and_central_trash_handler(qapp, window, tmp_path, monkeypatch):
    _scanned(window, qapp, tmp_path)
    observed = []
    original = main_module.ProjectsDialog
    def create(root, unit, policy, **kwargs):
        assert policy is window._cleanup_policy
        dialog = original(root, unit, policy, **kwargs)
        def execute():
            dialog.review_requested.emit([])
            return 0
        dialog.exec = execute
        return dialog
    monkeypatch.setattr(main_module, "ProjectsDialog", create)
    monkeypatch.setattr(window, "move_to_trash", observed.append)
    window.show_projects()
    assert observed == [[]]


def test_partial_coverage_label(qapp, project_tree):
    model = ProjectsModel()
    model.set_rows(projects(project_tree, partial=True).rows)
    assert model.index(0, 6).data() == "Incomplete"
