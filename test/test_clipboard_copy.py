"""Clipboard encoding yields, preserves text and rejects superseded pending copies."""

import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QThread, Qt, Signal
from PySide6.QtGui import QShortcut
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QApplication, QDialog, QTableView, QVBoxLayout
import pytest

from je_file_tree.core.node import Node
from je_file_tree.gui import grouped_list, list_transfer as transfer


class _Clipboard(QObject):
    dataChanged = Signal()  # noqa: N815 - QClipboard-compatible signal

    def __init__(self):
        super().__init__()
        self.text = 'before'
        self.writes = []

    def setText(self, value):  # noqa: N802 - QClipboard-compatible recording sink
        self.text = value
        self.writes.append(value)
        self.dataChanged.emit()


@pytest.fixture
def clipboard(qapp, monkeypatch):
    previous = getattr(qapp, '_filetree_clipboard_copy', None)
    if previous is not None:
        previous.cancel()
    monkeypatch.delattr(qapp, '_filetree_clipboard_copy', raising=False)
    sink = _Clipboard()
    monkeypatch.setattr(QApplication, 'clipboard', staticmethod(lambda: sink))
    yield sink
    owner = getattr(qapp, '_filetree_clipboard_copy', None)
    if owner is not None:
        owner.cancel()
        owner.deleteLater()
        delattr(qapp, '_filetree_clipboard_copy')


def _view(count, prefix='entry'):
    model = grouped_list.GroupedListModel()
    model.set_groups([('owned', [Node(f'{prefix}{row}', False) for row in range(count)])], 'auto')
    view = grouped_list.build_view(model)
    grouped_list.select_entries(model, view, skip_first=False)
    transfer.install_copy(view)
    return view, model


def _start(view):
    view.findChild(QShortcut).activated.emit()
    active = [capture for capture in view.findChildren(transfer.ListCapture) if capture._active]
    assert len(active) == 1
    active[0]._timer.stop()
    return active[0]


def _finish(capture):
    for _ in range(10000):
        capture._timer.stop()
        capture._chunk()
        if not capture._active:
            break
    assert not capture._active


def test_tsv_rows_are_encoded_during_capture_before_the_final_gui_turn(qapp, monkeypatch, clipboard):
    view, _model = _view(4096)
    calls, factory = [], csv.writer

    class Writer:
        def __init__(self, *args, **kwargs):
            self.writer = factory(*args, **kwargs)

        def writerow(self, row):
            calls.append(row)
            return self.writer.writerow(row)

    monkeypatch.setattr(csv, 'writer', Writer)
    monkeypatch.setattr(transfer, '_CHUNK_ROWS', 7)
    monkeypatch.setattr(transfer, '_CHUNK_SECONDS', 10)
    capture = _start(view)
    try:
        capture._chunk()
        assert 1 < len(calls) <= 8, len(calls)
        assert capture._active and not clipboard.writes and capture.rows
    finally:
        capture.cancel()
        view.deleteLater()


def test_a_new_copy_in_another_view_cancels_the_older_pending_copy(qapp, clipboard):
    first_view, _first_model = _view(1000, 'old')
    second_view, _second_model = _view(1, 'new')
    first = _start(first_view)
    second = _start(second_view)
    try:
        assert not first._active and second._active
        _finish(second)
        assert len(clipboard.writes) == 1 and 'new0' in clipboard.text and 'old0' not in clipboard.text
        first._chunk()
        assert len(clipboard.writes) == 1
    finally:
        first.cancel()
        second.cancel()
        first_view.deleteLater()
        second_view.deleteLater()


def test_incremental_text_matches_the_synchronous_oracle_and_publishes_on_gui_thread(qapp, clipboard):
    model = QStandardItemModel()
    header = ['=name', 'Folder', 'Other', 'Blank']
    model.setHorizontalHeaderLabels(header)
    rows = [['=2+2', '資料夾\twith\nnewline', '"quoted"\r\nvalue', ''],
            ['@link', '+sum', '-entry', "'=already"], ['plain', '零', '0', ' ']]
    for row in rows:
        model.appendRow([QStandardItem(cell) for cell in row])
    transfer.copy_table(tuple(header), rows)
    expected = clipboard.text
    clipboard.text, clipboard.writes = 'before', []
    view = QTableView()
    view.setModel(model)
    view.selectAll()
    transfer.install_copy(view)
    capture = _start(view)
    threads = []
    clipboard.dataChanged.connect(lambda: threads.append(QThread.currentThread()))
    _finish(capture)
    assert clipboard.text == expected and len(clipboard.writes) == 1
    assert threads == [qapp.thread()] and capture._output.closed
    assert list(csv.reader(io.StringIO(clipboard.text), delimiter='\t'))[1][0] == "'=2+2"
    assert qapp._filetree_clipboard_copy._current is None
    view.deleteLater()


@pytest.mark.parametrize('change', ['selection', 'data', 'clipboard', 'close', 'owner-hide', 'destroy', 'cancel'])
def test_pending_copy_cancellation_keeps_existing_clipboard_and_closes_buffer(qapp, monkeypatch, clipboard, change):
    owner = QDialog()
    view, model = _view(100)
    layout = QVBoxLayout(owner)
    layout.addWidget(view)
    if change == 'owner-hide':
        owner.show()
        qapp.processEvents()
    monkeypatch.setattr(transfer, '_CHUNK_ROWS', 7)
    capture = _start(view)
    capture._chunk()
    capture._timer.stop()
    assert capture.rows and not capture._output.closed
    if change == 'selection':
        view.selectionModel().clearSelection()
    elif change == 'data':
        model.set_unit('B')
    elif change == 'clipboard':
        clipboard.setText('external')
    elif change == 'close':
        owner.close()
    elif change == 'owner-hide':
        owner.hide()
    elif change == 'destroy':
        view.deleteLater()
        QCoreApplication.sendPostedEvents(view, QEvent.Type.DeferredDelete)
    else:
        qapp._filetree_clipboard_copy.cancel()
    assert not capture._active and capture._output.closed
    if change != 'destroy':
        assert not capture._timer.isActive()
    assert clipboard.text == ('external' if change == 'clipboard' else 'before')
    assert len(clipboard.writes) == (1 if change == 'clipboard' else 0)
    assert qapp._filetree_clipboard_copy._current is None
    owner.deleteLater()


def test_empty_selection_keeps_clipboard_and_releases_the_request(qapp, clipboard):
    view, _model = _view(0)
    capture = _start(view)
    _finish(capture)
    assert not clipboard.writes and clipboard.text == 'before' and capture._output.closed
    assert qapp._filetree_clipboard_copy._current is None
    view.deleteLater()


def test_obsolete_or_early_callbacks_cannot_publish_or_cancel_a_newer_copy(qapp, clipboard):
    view, _model = _view(100)
    first = _start(view)
    controller = qapp._filetree_clipboard_copy
    controller._publish(first, [['early']])
    assert not clipboard.writes and first._active
    second = _start(view)
    controller._publish(first, [['stale']])
    controller._finished(first)
    assert second._active and controller._current is second
    _finish(second)
    assert len(clipboard.writes) == 1 and second._output.closed and first._output.closed
    view.deleteLater()


def test_reentrant_new_copy_during_header_capture_supersedes_construction(qapp, monkeypatch, clipboard):
    first_view, first_model = _view(100, 'old')
    second_view, _second_model = _view(1, 'new')
    from je_file_tree.gui.clipboard_copy import _controller
    controller = _controller()
    original, armed = first_model.headerData, [True]

    def header(section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if armed:
            armed.pop()
            controller.copy(second_view)
        return original(section, orientation, role)

    monkeypatch.setattr(first_model, 'headerData', header)
    controller.copy(first_view)
    current = controller._current
    assert current is not None and current.view is second_view
    obsolete = first_view.findChild(transfer.ListCapture)
    assert not obsolete._active and obsolete._output.closed
    _finish(current)
    assert len(clipboard.writes) == 1 and 'new0' in clipboard.text and 'old0' not in clipboard.text
    first_view.deleteLater()
    second_view.deleteLater()


def test_actual_application_quit_cancels_and_releases_pending_copy_in_owned_child():
    script = """
import json
from PySide6.QtCore import QObject,QTimer,Signal
from PySide6.QtWidgets import QApplication
from je_file_tree.core.node import Node
from je_file_tree.gui.grouped_list import GroupedListModel,build_view,select_entries
from je_file_tree.gui.clipboard_copy import _controller
class Sink(QObject):
    dataChanged=Signal()
    writes=[]
    def setText(self,text): self.writes.append(text);self.dataChanged.emit()
app=QApplication([]);sink=Sink();QApplication.clipboard=staticmethod(lambda:sink)
model=GroupedListModel();model.set_groups([('owned',[Node(str(i),False) for i in range(10000)])],'auto')
view=build_view(model);select_entries(model,view,skip_first=False)
owner=_controller();owner.copy(view);capture=owner._current
QTimer.singleShot(0,app.quit)
code=app.exec()
print(json.dumps({'exit':code,'active':capture._active,'closed':capture._output.closed,
                  'current_none':owner._current is None,'writes':len(sink.writes)}))
"""
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen',
                       PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result = subprocess.run(  # noqa: S603 - fresh owned offscreen app, in-memory rows and recording clipboard
        [sys.executable, '-c', script], capture_output=True, env=environment, timeout=20, check=True)
    assert json.loads(result.stdout) == {'exit': 0, 'active': False, 'closed': True, 'current_none': True, 'writes': 0}


@pytest.mark.parametrize('observer_first', [False, True])
def test_a_copy_started_by_a_publication_observer_survives_the_older_completion(qapp, clipboard, observer_first):
    first_view, _first_model = _view(1, 'first')
    second_view, _second_model = _view(1, 'second')
    def observe():
        if len(clipboard.writes) == 1:
            qapp._filetree_clipboard_copy.copy(second_view)

    if observer_first:
        clipboard.dataChanged.connect(observe)
    first = _start(first_view)
    controller = qapp._filetree_clipboard_copy
    if not observer_first:
        clipboard.dataChanged.connect(observe)
    _finish(first)
    second = controller._current
    assert second is not None and second._active and second is not first
    _finish(second)
    assert len(clipboard.writes) == 2 and 'second0' in clipboard.text and controller._current is None
    first_view.deleteLater()
    second_view.deleteLater()


def test_clipboard_change_during_row_encoding_does_not_write_to_closed_buffer(qapp, monkeypatch, clipboard):
    from je_file_tree.gui import clipboard_copy
    view, _model = _view(100)
    capture = _start(view)
    original, armed = clipboard_copy.spreadsheet_text, [True]

    def escape(cell):
        if armed:
            armed.pop()
            clipboard.setText('external')
        return original(cell)

    monkeypatch.setattr(clipboard_copy, 'spreadsheet_text', escape)
    capture._chunk()
    assert not capture._active and capture._output.closed and not capture.rows
    assert clipboard.writes == ['external'] and qapp._filetree_clipboard_copy._current is None
    view.deleteLater()


def test_clipboard_change_after_completion_before_publication_keeps_external_text(qapp, monkeypatch, clipboard):
    view, _model = _view(1)
    capture = _start(view)
    original = capture.encoded_text

    def encoded():
        clipboard.setText('external')
        return original()

    monkeypatch.setattr(capture, 'encoded_text', encoded)
    _finish(capture)
    assert clipboard.writes == ['external'] and capture._output.closed
    assert qapp._filetree_clipboard_copy._current is None
    view.deleteLater()
