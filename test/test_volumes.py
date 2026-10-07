"""Volume scalar rows preserve sorting/unknowns and own Stop, close and scan activation."""

from types import SimpleNamespace

from PySide6.QtCore import QByteArray, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

from test_gui import _wait, window as window  # noqa: PLC0414 - explicit fixture re-export
from je_file_tree.core.trash_size import TrashUsage
from je_file_tree.gui import main_window as main_module
from je_file_tree.gui import volumes
from je_file_tree.gui.tables import SORT_ROLE


def _storage(root="D:/", *, free=400, available=300, ready=True):
    return SimpleNamespace(refresh=lambda: None, isValid=lambda: True, isReady=lambda: ready,
                           rootPath=lambda: root, displayName=lambda: "owned drive",
                           fileSystemType=lambda: QByteArray(b"ntfs"),
                           bytesTotal=lambda: 1000, bytesFree=lambda: free, bytesAvailable=lambda: available)


def _sources(monkeypatch, storage=None):
    monkeypatch.setattr(volumes.QStorageInfo, "mountedVolumes", lambda: storage or [_storage()])
    monkeypatch.setattr(volumes, "trash_usage", lambda *_args, **_kwargs: TrashUsage(123, 2, True))
    monkeypatch.setattr(volumes, "allocation_unit", lambda _root: 4096)


def test_native_bar_numeric_sort_and_reserved_available_space(qapp, monkeypatch):
    _sources(monkeypatch, [_storage("D:/"), _storage("E:/", free=600, available=600), _storage(ready=False)])
    dialog = volumes.VolumesDialog("auto")
    try:
        _wait(qapp, lambda: not dialog.worker.isRunning())
        row = dialog.model.row_at(0)
        assert row.used == 600 and row.available == 300
        assert dialog.model.index(0, 7).data() == "123 B"
        dialog.proxy.sort(5, Qt.SortOrder.DescendingOrder)
        assert dialog.proxy.index(0, 0).data() == "E:/"
        assert dialog.proxy.index(0, 5).data(SORT_ROLE) == 600
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        dialog.show()
        qapp.processEvents()
        assert not dialog.grab().isNull()
        requested = []
        dialog.scan_requested.connect(requested.append)
        dialog._scan(dialog.proxy.index(0, 0))
        assert requested == ["E:/"] and not dialog.worker.isRunning()
    finally:
        dialog.reject()
        dialog.deleteLater()


def test_unknown_capacity_cluster_and_partial_trash_remain_unknown(qapp, monkeypatch):
    _sources(monkeypatch, [_storage(free=-1, available=-1)])
    monkeypatch.setattr(volumes, "trash_usage", lambda *_args, **_kwargs: TrashUsage(10, 1, False, "denied"))
    monkeypatch.setattr(volumes, "allocation_unit", lambda _root: None)
    dialog = volumes.VolumesDialog("auto")
    try:
        _wait(qapp, lambda: not dialog.worker.isRunning())
        assert dialog.model.row_at(0).used is None and dialog.model.row_at(0).available is None
        assert "unknown" in dialog.model.index(0, 6).data().lower()
        assert "Unknown total" in dialog.model.index(0, 7).data()
        assert dialog.model.index(0, 7).data(Qt.ItemDataRole.ToolTipRole) == "denied"
        assert not dialog.model.flags(dialog.model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    finally:
        dialog.reject()
        dialog.deleteLater()


def test_stop_and_close_suppress_queued_results(qapp, monkeypatch):
    _sources(monkeypatch)
    dialog = volumes.VolumesDialog("auto")
    dialog.stop()
    _wait(qapp, lambda: not dialog.worker.isRunning())
    dialog._show([], 10)
    assert not dialog.model.rows()
    dialog.reject()
    dialog._show([], 10)
    assert not dialog.model.rows() and dialog._closed
    dialog.deleteLater()


def test_volume_rows_are_bounded_with_complete_count(qapp, monkeypatch):
    _sources(monkeypatch, [_storage(str(number)) for number in range(300)])
    calls = []
    monkeypatch.setattr(volumes, "trash_usage", lambda root, **_kwargs: calls.append(root) or TrashUsage(0, 0, True))
    dialog = volumes.VolumesDialog("auto")
    try:
        _wait(qapp, lambda: not dialog.worker.isRunning())
        assert dialog.model.rowCount() == 256 and len(calls) == 256
        assert "300" in dialog.status.text()
    finally:
        dialog.reject()
        dialog.deleteLater()


def test_free_space_bar_requests_horizontal_native_rendering(qapp, monkeypatch):
    model = volumes.VolumesModel()
    model.set_rows([volumes.Volume("D:/", "owned", "NTFS", 1000, 600, 300, 4096, TrashUsage(0, 0, True))])
    rendered = []
    style = SimpleNamespace(drawControl=lambda control, bar, _painter: rendered.append((control, bar)))
    monkeypatch.setattr(volumes.QApplication, "style", lambda: style)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 190, 30)
    volumes.FreeSpaceDelegate().paint(None, option, model.index(0, 5))
    control, bar = rendered[0]
    assert control == QStyle.ControlElement.CE_ProgressBar
    assert bar.state & QStyle.StateFlag.State_Horizontal
    assert bar.progress == 300 and bar.rect.width() > bar.rect.height()
    assert "30%" in bar.text and bar.textVisible


def test_welcome_and_view_share_the_scan_root_controller(qapp, window, monkeypatch):
    _sources(monkeypatch)
    requested = []
    monkeypatch.setattr(window, "start_scan", requested.append)
    def execute(dialog):
        _wait(qapp, lambda: not dialog.worker.isRunning())
        dialog._scan(dialog.proxy.index(0, 0))
        return 0
    monkeypatch.setattr(main_module.VolumesDialog, "exec", execute)
    window._actions["volumes"].trigger()
    QTest.mouseClick(window.welcome._overview, Qt.MouseButton.LeftButton)
    assert requested == ["D:/", "D:/"]
