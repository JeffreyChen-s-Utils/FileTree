"""One-page printing of owned view pixels, preserving aspect ratio and printable margins."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtPrintSupport import QPrinter


def view_printer(image: QImage) -> QPrinter:
    """Create a printer with an A4 orientation fitting the current captured view."""
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setDocName("FileTree")
    printer.setPageLayout(_view_layout(image))
    return printer


def _view_layout(image: QImage) -> QPageLayout:
    orientation = (QPageLayout.Orientation.Landscape if image.width() > image.height()
                   else QPageLayout.Orientation.Portrait)
    return QPageLayout(QPageSize(QPageSize.PageSizeId.A4), orientation,
                      QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)


def fit_view(image: QImage, page: QRectF) -> QRectF:
    """Fit the complete capture inside a printable rectangle, without cropping or distortion."""
    if image.isNull() or page.width() <= 0 or page.height() <= 0:
        raise ValueError("empty view or printable page")
    scale = min(page.width() / image.width(), page.height() / image.height())
    width, height = image.width() * scale, image.height() * scale
    return QRectF(page.x() + (page.width() - width) / 2, page.y() + (page.height() - height) / 2, width, height)


def print_view(image: QImage, printer: QPrinter | QPdfWriter) -> None:
    """Print exactly the captured visible view on one page; callers own any print dialog."""
    rect = printer.pageLayout().paintRectPixels(printer.resolution())
    target = fit_view(image, QRectF(0, 0, rect.width(), rect.height()))
    painter = QPainter(printer)
    if not painter.isActive():
        raise OSError("printer painter could not start")
    try:
        painter.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.LosslessImageRendering)
        painter.drawImage(target, image)
    finally:
        if not painter.end():
            raise OSError("printer output could not finish")


def save_view_pdf(image: QImage, target: str) -> int:
    """Write Qt PDF without querying native printers; atomically replace a completed temporary sibling."""
    path = Path(target)
    descriptor, temporary = tempfile.mkstemp(prefix=".filetree-pdf-", suffix=".pdf", dir=path.parent)
    os.close(descriptor)
    try:
        printer = QPdfWriter(temporary)
        printer.setResolution(300)
        printer.setTitle("FileTree")
        printer.setCreator("FileTree")
        printer.setPageLayout(_view_layout(image))
        print_view(image, printer)
        del printer  # Close the engine before replacement on Windows.
        with Path(temporary).open("r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return 1
