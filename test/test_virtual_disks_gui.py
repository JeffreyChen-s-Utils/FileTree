"""Virtual-disk inventory/header review stays read-only, bounded and joined at Stop/close."""

from dataclasses import replace
import sys
import threading
from types import SimpleNamespace

from PySide6.QtCore import Qt

from test_gui import _wait, window as window  # noqa: PLC0414
from je_file_tree.core.scanner import scan
from je_file_tree.core.virtual_disks import find_virtual_disks, VirtualDisks
from je_file_tree.core.virtual_disk_info import VirtualDiskInfo
from je_file_tree.gui import virtual_disks as gui
from je_file_tree.gui.scan_worker import analyse


def _fixture(tmp_path, monkeypatch):
    for kind in ("vhdx", "qcow2"):
        (tmp_path / ("中文 owned." + kind)).write_bytes(b"owned test bytes")
    root = scan(tmp_path).root
    inventory = find_virtual_disks(root, registrations=[])
    monkeypatch.setattr(gui, "find_virtual_disks", lambda *_args, **_kwargs: inventory)
    return root, inventory


def _select(dialog, disk):
    index = next(i for i, row in enumerate(dialog.model.rows()) if row.disk is disk)
    dialog.view.setCurrentIndex(dialog.proxy.mapFromSource(dialog.model.index(index, 0)))


def test_inventory_never_queries_headers_guest_unknown_and_exact_node_activation(window, qapp, tmp_path, monkeypatch):
    root, inventory = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(gui, "inspect_virtual_disk", lambda *_args, **_kw: (_ for _ in ()).throw(
        AssertionError("Automatic inventory must not query a native header")))
    before = [(node.path, node.snapshot, node.size, node.allocated) for node in root.children]
    dialog = gui.VirtualDisksDialog(root, "auto", window)
    _wait(qapp, lambda: dialog.model.rowCount() == 2 and not dialog.worker.isRunning())
    assert "中文" in dialog.model.index(0, 0).data()
    assert dialog.model.index(0, 7).data() == gui.tr("size_unknown")
    assert not dialog.model.flags(dialog.model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    disk = next(disk for disk in inventory.rows if disk.kind == "qcow2")
    _select(dialog, disk)
    assert not dialog.info_button.isEnabled() and dialog.select_button.isEnabled()
    assert gui._state(dialog._current()) == gui.tr("vd_unsupported")
    selected = []
    dialog.selected.connect(selected.append)
    dialog.select_recorded()
    assert selected == [disk.node] and not dialog.worker.isRunning()
    assert before == [(node.path, node.snapshot, node.size, node.allocated) for node in root.children]
    dialog.deleteLater()


def test_explicit_header_query_preserves_recorded_bytes_and_reports_separate_native_fields(
        window, qapp, tmp_path, monkeypatch):
    root, inventory = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(gui, "sys", SimpleNamespace(platform="win32"))
    disk = next(disk for disk in inventory.rows if disk.kind == "vhdx")
    called = []
    info = VirtualDiskInfo(disk, (), 67108864, 4194304, 3, False, bytes(range(16)))
    def header(captured, **_kwargs):
        called.append(captured)
        return info
    monkeypatch.setattr(gui, "inspect_virtual_disk", header)
    dialog = gui.VirtualDisksDialog(root, "auto", window)
    _wait(qapp, lambda: dialog.model.rowCount() == 2 and not dialog.worker.isRunning())
    assert not called
    _select(dialog, disk)
    assert dialog.info_button.isEnabled()
    dialog.inspect_selected()
    _wait(qapp, lambda: dialog.info_worker is None)
    row = next(row for row in dialog.model.rows() if row.disk is disk)
    assert called == [disk] and row.info is info and not row.error
    assert gui._amount(row, "virtual_size") == 67108864 and gui._amount(row, "physical_size") == 4194304
    assert gui._amount(row, "size") == len(b"owned test bytes") and gui._amount(row, "guest_used") is None
    assert root.children[0].size == len(b"owned test bytes")
    assert "03020100-0504-0706-0809-0a0b0c0d0e0f" in dialog.model.extra_data(row, Qt.ItemDataRole.ToolTipRole)
    assert dialog.status.textFormat() == Qt.TextFormat.PlainText
    dialog.reject()
    dialog.deleteLater()


def test_header_failure_is_literal_and_external_provider_has_no_tree_action(window, qapp, tmp_path, monkeypatch):
    root, inventory = _fixture(tmp_path, monkeypatch)
    disk = next(disk for disk in inventory.rows if disk.kind == "vhdx")
    external = replace(disk, node=None, source="wsl", name="Owned external")
    monkeypatch.setattr(gui, "find_virtual_disks", lambda *_args, **_kwargs: VirtualDisks((external,), 1, 2, True))
    monkeypatch.setattr(gui, "sys", SimpleNamespace(platform="win32"))
    def denied(*_args, **_kwargs):
        raise OSError("<b>native refusal</b>")
    monkeypatch.setattr(gui, "inspect_virtual_disk", denied)
    dialog = gui.VirtualDisksDialog(root, "auto", window, partial=True)
    _wait(qapp, lambda: dialog.model.rowCount() == 1 and not dialog.worker.isRunning())
    _select(dialog, external)
    assert not dialog.select_button.isEnabled()
    dialog.inspect_selected()
    _wait(qapp, lambda: dialog.info_worker is None)
    assert dialog.model.rows()[0].info is None and dialog.model.rows()[0].error == "<b>native refusal</b>"
    assert "<b>native refusal</b>" in dialog.status.text() and dialog.status.textFormat() == Qt.TextFormat.PlainText
    dialog.reject()
    dialog.deleteLater()


def test_stop_close_joins_inventory_and_ignores_late_rows(window, qapp, tmp_path, monkeypatch):
    root, inventory = _fixture(tmp_path, monkeypatch)
    entered = threading.Event()
    def inventory_read(_root, *, cancel, **_kwargs):
        entered.set()
        assert cancel.wait(10)
        return inventory
    monkeypatch.setattr(gui, "find_virtual_disks", inventory_read)
    dialog = gui.VirtualDisksDialog(root, "auto", window)
    _wait(qapp, entered.is_set)
    dialog.stop()
    dialog.reject()
    dialog._show(inventory)
    assert not dialog.worker.isRunning() and dialog.model.rowCount() == 0
    dialog.deleteLater()


def test_stop_close_joins_native_header_and_suppresses_late_information(window, qapp, tmp_path, monkeypatch):
    root, inventory = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(gui, "sys", SimpleNamespace(platform="win32"))
    disk = next(disk for disk in inventory.rows if disk.kind == "vhdx")
    entered = threading.Event()
    info = VirtualDiskInfo(disk, (), 67108864, 4194304, 3, False, None)
    def header(_disk, *, cancel):
        entered.set()
        assert cancel.wait(10)
        return info
    monkeypatch.setattr(gui, "inspect_virtual_disk", header)
    dialog = gui.VirtualDisksDialog(root, "auto", window)
    _wait(qapp, lambda: dialog.model.rowCount() == 2 and not dialog.worker.isRunning())
    _select(dialog, disk)
    dialog.inspect_selected()
    _wait(qapp, entered.is_set)
    worker = dialog.info_worker
    dialog.reject()
    dialog._information(worker, info, "")
    assert not worker.isRunning() and all(row.info is None for row in dialog.model.rows())
    dialog.deleteLater()


def test_main_window_requires_results_serializes_owned_dialog_and_joins_at_close(window, sample_tree, monkeypatch):
    assert window._actions["virtual_disks"].isVisible()
    assert not window._actions["virtual_disks"].isEnabled()
    window.results.show_outcome(analyse(scan(sample_tree)))
    window._update_actions()
    assert window._actions["virtual_disks"].isEnabled()
    entered = []
    def execute(dialog):
        entered.append(dialog)
        assert dialog in window._path_dialogs and window.operation_busy
        window.start_scan(str(sample_tree))
        assert window._worker is None
        dialog.reject()
        assert dialog._closed and not dialog.worker.isRunning()
        return 0
    monkeypatch.setattr(gui.VirtualDisksDialog, "exec", execute)
    window.show_virtual_disks()
    assert len(entered) == 1 and not window._path_dialogs and not window.operation_busy
    assert gui.sys.platform == sys.platform
