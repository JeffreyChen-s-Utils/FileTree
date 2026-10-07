"""Installation metadata is read-only, cancellable and never launches registry uninstall commands."""

import sys
import threading

from PySide6.QtCore import Qt

from test_gui import _wait, window as window  # noqa: PLC0414
from je_file_tree.core import programs as core
from je_file_tree.core.programs import Program, Programs
from je_file_tree.core.scanner import scan
from je_file_tree.gui import programs
from je_file_tree.gui.programs import ProgramsDialog
from je_file_tree.gui.scan_worker import analyse


def test_readonly_installation_table_fixed_os_page_and_exact_tree_activation(window, qapp, sample_tree, monkeypatch):
    root = scan(sample_tree).root
    folder = next(child for child in root.children if child.name == "photos")
    row = Program("中文 Game", "v1", "Publisher", "steam", folder.path, 99999, folder, True)
    monkeypatch.setattr(programs, "installed_programs", lambda *_args, **_kwargs: Programs([row], 1, 0))
    dialog = ProgramsDialog(root, "auto", window)
    _wait(qapp, lambda: dialog.model.rowCount() == 1)
    assert dialog.model.index(0, 0).data() == "中文 Game"
    assert not dialog.model.flags(dialog.model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    opened, selected = [], []
    monkeypatch.setattr(programs.sys, "platform", "win32")
    monkeypatch.setattr(programs.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) and True)
    dialog.open_uninstall_page()
    assert opened == ["ms-settings:appsfeatures"]
    dialog.selected.connect(selected.append)
    dialog._select(dialog.proxy.index(0, 0))
    assert selected == [folder] and not dialog.worker.isRunning()
    dialog.deleteLater()


def test_stop_close_join_and_late_inventory_is_ignored(window, qapp, sample_tree, monkeypatch):
    entered = threading.Event()

    def waiting(_root, *, cancel, **_kwargs):
        entered.set()
        assert cancel.wait(10)
        return Programs([], 0, 0)

    monkeypatch.setattr(programs, "installed_programs", waiting)
    dialog = ProgramsDialog(scan(sample_tree).root, "auto", window)
    _wait(qapp, entered.is_set)
    dialog.stop()
    dialog.reject()
    dialog._show(Programs([Program("late", "", "", "registry", "", 4096)], 1, 0))
    assert not dialog.worker.isRunning() and dialog.model.rowCount() == 0
    dialog.deleteLater()


def test_windows_only_action_requires_completed_results(window, sample_tree):
    assert window._actions["programs"].isVisible() == (sys.platform == "win32")
    assert not window._actions["programs"].isEnabled()
    window.results.show_outcome(analyse(scan(sample_tree)))
    window._update_actions()
    assert window._actions["programs"].isEnabled()
    assert core.installed_programs(window.results.outcome.result.root) is not None
