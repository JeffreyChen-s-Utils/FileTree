"""Capture on the GUI thread, encode/write atomic PNG or vector SVG on an export worker."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPoint, QRect, QSaveFile
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgGenerator

from je_file_tree.gui.charts import BARS, SUNBURST, ChartStack

SVG_MODES = (BARS, SUNBURST)


def capture_svg(charts: ChartStack) -> bytes:
    """Render full bounded bars/rings as real vector paths/text on the GUI thread."""
    if charts.mode not in SVG_MODES:
        raise ValueError("SVG is available for bars and sunburst")
    chart = charts.current_chart()
    data = QByteArray()
    buffer = QBuffer(data)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(buffer.errorString())
    generator = QSvgGenerator()
    generator.setOutputDevice(buffer)
    generator.setSize(chart.size())
    generator.setViewBox(QRect(0, 0, chart.width(), chart.height()))
    painter = QPainter(generator)
    if not painter.isActive():
        raise OSError("SVG painter could not start")
    try:
        if charts.mode == SUNBURST:
            charts.sunburst.draw_vector(painter)
        else:
            chart.render(painter, QPoint())
    finally:
        painter.end()
        buffer.close()
    return bytes(data)


def save_graphic(target: str, graphic: QImage | bytes) -> int:
    """Encode an owned PNG image or SVG bytes, then atomically replace the requested file."""
    if isinstance(graphic, QImage):
        data = QByteArray()
        buffer = QBuffer(data)
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not graphic.save(buffer, "PNG"):
            raise OSError("PNG encoding failed")
        buffer.close()
        graphic = bytes(data)
    file = QSaveFile(target)
    file.setDirectWriteFallback(False)
    if not file.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(file.errorString())
    if file.write(graphic) != len(graphic):
        file.cancelWriting()
        raise OSError(file.errorString())
    if not file.commit():
        raise OSError(file.errorString())
    return 1
