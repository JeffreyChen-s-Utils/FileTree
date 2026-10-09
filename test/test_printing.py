"""One-page QPrinter output fits the current capture, and failed writes preserve earlier PDFs."""

import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QDialog, QFileDialog

from test_gui import _wait
from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.scanner import scan
from je_file_tree.gui import printing
from je_file_tree.gui import main_window as module
from je_file_tree.gui.printing import fit_view, save_view_pdf
from je_file_tree.gui.scan_worker import ExportWorker, analyse, wait_for


def _image():
    image = QImage(800, 400, QImage.Format.Format_RGB32)
    image.fill(QColor("#175cac"))
    return image


def test_view_fits_inside_printable_page_without_stretching_or_cropping() -> None:
    target = fit_view(_image(), QRectF(10, 20, 100, 100))
    assert target == QRectF(10, 45, 100, 50)
    with pytest.raises(ValueError):
        fit_view(QImage(), QRectF(0, 0, 100, 100))


def test_pdf_worker_produces_one_fitted_page_and_can_be_joined(qapp, tmp_path) -> None:
    target = tmp_path / "view.pdf"
    done, threads = [], []

    def save():
        threads.append(threading.get_ident())
        return save_view_pdf(_image(), str(target))

    worker = ExportWorker(save)
    worker.done.connect(done.append)
    worker.start()
    _wait(qapp, lambda: bool(done))
    wait_for(worker)
    assert threads[0] != threading.get_ident() and target.read_bytes().startswith(b"%PDF-")
    document = QPdfDocument()
    assert document.load(str(target)) == QPdfDocument.Error.None_
    assert document.pageCount() == 1
    size = document.pagePointSize(0)
    assert size.width() > size.height()
    image = document.render(0, QSize(600, 425))
    assert not image.isNull()
    assert image.pixelColor(300, 212).name() == "#175cac"
    assert image.pixelColor(5, 5).alpha() == 0, "the paper margin remains unpainted"
    document.close()
    worker.deleteLater()


def test_failed_pdf_generation_preserves_existing_output_and_removes_only_its_temp(qapp, tmp_path, monkeypatch) -> None:
    target = tmp_path / "view.pdf"
    target.write_bytes(b"previous PDF")

    def fail(image, printer):
        raise OSError("printer failure")

    monkeypatch.setattr(printing, "print_view", fail)
    with pytest.raises(OSError):
        save_view_pdf(_image(), str(target))
    assert target.read_bytes() == b"previous PDF" and not list(tmp_path.glob(".filetree-pdf-*"))


def test_print_dialog_cancel_never_submits_a_job_and_accepted_job_uses_owned_pixels(
        window, tmp_path, monkeypatch) -> None:
    window.results.show_outcome(analyse(scan(tmp_path)))
    captured, printed = [], []
    monkeypatch.setattr(module, "view_printer", lambda image: captured.append(image) or object())
    monkeypatch.setattr(module, "print_view", lambda image, printer: printed.append(image))
    monkeypatch.setattr(module, "QPrintDialog", lambda *args: SimpleNamespace(exec=lambda: QDialog.DialogCode.Rejected))
    window.print_current_view()
    assert captured and not printed
    monkeypatch.setattr(module, "QPrintDialog", lambda *args: SimpleNamespace(exec=lambda: QDialog.DialogCode.Accepted))
    window.print_current_view()
    assert printed == [captured[-1]] and not printed[0].isNull()


def test_cancelled_pdf_dialog_leaves_no_worker_or_file(window, tmp_path, monkeypatch) -> None:
    window.results.show_outcome(analyse(scan(tmp_path)))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    window.export_view_pdf()
    assert not window._exports and not list(tmp_path.glob("*.pdf"))
