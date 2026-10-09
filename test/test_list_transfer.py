"""Displayed list order, safe clipboard text, bounded streaming and atomic cancellation."""

import csv
import io
import threading

import pytest
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QTableView

from test_gui import _wait
from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.export import export_table_csv
from je_file_tree.core.scanner import scan
from je_file_tree.gui.list_transfer import ListCapture, ListStream, copy_table, install_copy
from je_file_tree.gui.main_window import RESULTS_PAGE
from je_file_tree.gui.results_view import AGE_TAB, LARGEST_TAB, SEARCH_TAB, TYPES_TAB
from je_file_tree.gui.scan_worker import ExportWorker, analyse, wait_for


def _view(count=2):
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(['Name', 'Size'])
    for number in range(count):
        model.appendRow([QStandardItem(str(number)), QStandardItem('10 B')])
    view = QTableView()
    view.setModel(model)
    return view, model


def test_copy_is_quoted_tsv_and_escapes_formula_text(qapp) -> None:
    copy_table(('Name', 'Folder'), [['=2+2', '資料夾\twith\nnewline'], ['@link', '+sum']])
    rows = list(csv.reader(io.StringIO(QApplication.clipboard().text()), delimiter='\t'))
    assert rows == [['Name', 'Folder'], ["'=2+2", '資料夾\twith\nnewline'], ["'@link", "'+sum"]]
    previous = QApplication.clipboard().text()
    copy_table(('Name',), [])
    assert QApplication.clipboard().text() == previous


def test_model_capture_yields_and_aborts_after_reset(qapp) -> None:
    view, model = _view(1000)
    capture = ListCapture(view, view)
    errors, ready = [], []
    capture.failed.connect(errors.append)
    capture.ready.connect(lambda *_: ready.append(True))
    capture.start()
    capture._timer.stop()
    capture._chunk()
    assert 0 < len(capture.rows) <= 128
    model.clear()
    assert len(errors) == 1 and not ready and not capture._active and not capture.rows
    capture.deleteLater()
    view.deleteLater()


def test_grouped_capture_preserves_headers_children_and_proxy_sorting(qapp) -> None:
    view, model = _view(0)
    head = QStandardItem('同じ content')
    head.appendRow([QStandardItem('child'), QStandardItem('15 B')])
    model.appendRow(head)
    capture, ready = ListCapture(view, view), []
    capture.ready.connect(lambda header, rows: ready.append((header, rows)))
    capture.start()
    _wait(qapp, lambda: bool(ready))
    assert ready[0] == (('Name', 'Size'), [['同じ content', ''], ['child', '15 B']])
    capture.deleteLater()
    view.deleteLater()


def test_ctrl_c_copies_only_selected_rows_in_model_order(qapp) -> None:
    view, model = _view(4)
    install_copy(view)
    view.show()
    view.activateWindow()
    view.setFocus()
    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    for number in (3, 1):
        view.selectionModel().select(model.index(number, 0), flags)
    QApplication.clipboard().setText('before')
    qapp.processEvents()
    QTest.keyClick(view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    _wait(qapp, lambda: QApplication.clipboard().text() != 'before')
    assert list(csv.reader(io.StringIO(QApplication.clipboard().text()), delimiter='\t')) == [
        ['Name', 'Size'], ['1', '10 B'], ['3', '10 B']]
    view.close()
    view.deleteLater()


def test_stream_is_bounded_and_cancel_preserves_target(qapp, tmp_path) -> None:
    stream = ListStream()
    for _ in range(8):
        assert stream.offer([['name']])
    assert not stream.offer([['more']])
    target = tmp_path / 'old.csv'
    target.write_text('keep', encoding='utf-8')
    stream.finish('changed')
    with pytest.raises(ValueError, match='changed'):
        export_table_csv(('Name',), stream.rows(), target)
    assert target.read_text(encoding='utf-8') == 'keep'
    assert list(tmp_path.iterdir()) == [target]


def test_streamed_worker_writes_all_rows_off_gui_thread(qapp, tmp_path) -> None:
    view, _model = _view(1200)
    stream, threads, finished = ListStream(), [], []
    capture = ListCapture(view, view, stream=stream)
    target = tmp_path / 'rows.csv'

    def write():
        threads.append(threading.get_ident())
        return export_table_csv(capture.header, stream.rows(), target)

    worker = ExportWorker(write)
    worker.done.connect(finished.append)
    worker.start()
    capture.start()
    _wait(qapp, lambda: bool(finished))
    wait_for(worker)
    assert threads == [threads[0]] and threads[0] != threading.get_ident()
    assert finished == [1200] and not capture.rows and stream.queue.qsize() <= 8
    with target.open(encoding='utf-8-sig', newline='') as source:
        rows = list(csv.reader(source))
    assert rows[0] == ['Name', 'Size'] and rows[-1] == ['1199', '10 B']
    capture.deleteLater()
    view.deleteLater()


def test_cancel_while_writer_waits_for_a_batch_preserves_the_existing_file(qapp, tmp_path, monkeypatch) -> None:
    stream = ListStream()
    reached, failures = threading.Event(), []
    get = stream.queue.get

    def waiting(*, timeout):
        reached.set()
        return get(timeout=timeout)

    monkeypatch.setattr(stream.queue, 'get', waiting)
    target = tmp_path / 'before.csv'
    target.write_text('keep', encoding='utf-8')
    worker = ExportWorker(lambda: export_table_csv(('Name',), stream.rows(), target))
    worker.failed.connect(failures.append)
    worker.start()
    assert reached.wait(2)
    stream.finish('cancelled during wait')
    wait_for(worker)
    qapp.processEvents()
    assert failures == ['cancelled during wait'] and target.read_text(encoding='utf-8') == 'keep'
    assert list(tmp_path.iterdir()) == [target]


def test_current_list_exports_filtered_display_order_and_all_tabs(window, qapp, sample_tree, monkeypatch, tmp_path):
    window.results.show_outcome(analyse(scan(sample_tree)))
    window.pages.setCurrentIndex(RESULTS_PAGE)
    for tab, view in ((SEARCH_TAB, window.results.search_table), (TYPES_TAB, window.results.types_table),
                      (AGE_TAB, window.results.age_table)):
        window.results.tabs.setCurrentIndex(tab)
        assert window.results.current_list() is view and window._actions['export_list'].isEnabled()
    window.results.tabs.setCurrentIndex(LARGEST_TAB)
    window.results._largest_filter.setText('big.bin')
    target = tmp_path / 'list.csv'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_args: (str(target), ''))
    window.export_list()
    _wait(qapp, lambda: not window._exports and not window._captures)
    with target.open(encoding='utf-8-sig', newline='') as source:
        rows = list(csv.reader(source))
    assert len(rows) == 2 and rows[1][0] == 'big.bin' and rows[1][1] == '500 B'


def test_close_cancels_producer_before_joining_stream_writer(window, qapp, monkeypatch, tmp_path) -> None:
    target = tmp_path / 'unchanged.csv'
    target.write_text('keep', encoding='utf-8')
    view, _model = _view(2000)
    stream = ListStream()
    capture = ListCapture(view, window, stream=stream)
    window._captures.add(capture)
    worker = ExportWorker(lambda: export_table_csv(capture.header, stream.rows(), target), window)
    window._exports.add(worker)
    worker.start()
    capture.start()
    window.close()
    assert not worker.isRunning() and target.read_text(encoding='utf-8') == 'keep'
    assert not list(tmp_path.glob('.file-tree-*'))
    view.deleteLater()
