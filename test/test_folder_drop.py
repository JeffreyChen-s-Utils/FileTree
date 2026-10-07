"""Scanning a dropped folder never negotiates permission to remove its source."""

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export


def test_shift_move_is_negotiated_as_copy_without_changing_the_source(window, tmp_path, monkeypatch):
    source = tmp_path / "資料夾 with space"
    source.mkdir()
    payload = source / "kept.txt"
    payload.write_bytes(b"keep the original")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(source))])
    actions = Qt.DropAction.CopyAction | Qt.DropAction.MoveAction
    entered = QDragEnterEvent(QPoint(10, 10), actions, mime,
                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier)
    dropped = QDropEvent(QPointF(10, 10), actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier)
    assert entered.proposedAction() == dropped.proposedAction() == Qt.DropAction.MoveAction
    scans = []
    monkeypatch.setattr(window, "start_scan", scans.append)
    window.dragEnterEvent(entered)
    window.dropEvent(dropped)
    assert entered.isAccepted() and dropped.isAccepted()
    assert entered.dropAction() == dropped.dropAction() == Qt.DropAction.CopyAction
    assert scans == [str(source)]
    assert payload.read_bytes() == b"keep the original"


def test_move_only_drag_is_ignored_and_does_not_start_a_scan(window, tmp_path, monkeypatch):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path))])
    scans = []
    monkeypatch.setattr(window, "start_scan", scans.append)
    entered = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.MoveAction, mime,
                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    dropped = QDropEvent(QPointF(10, 10), Qt.DropAction.MoveAction, mime,
                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.dragEnterEvent(entered)
    window.dropEvent(dropped)
    assert not entered.isAccepted() and not dropped.isAccepted()
    assert scans == []
