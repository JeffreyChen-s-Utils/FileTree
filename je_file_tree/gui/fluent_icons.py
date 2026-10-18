"""Line icons in the Fluent manner, drawn at run time in a palette colour (no image files).

Each icon is a list of strokes on a 24-unit grid; ``icon`` paints them with round caps at several
pixel sizes, in the given colour for normal use and a muted colour when disabled. Callers repaint
icons when the palette changes, so they always match the theme, high contrast included.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap

_SIZES = (16, 20, 24, 32, 40, 48)


def _lines(*points: tuple[float, float]) -> QPainterPath:
    path = QPainterPath(QPointF(*points[0]))
    for point in points[1:]:
        path.lineTo(QPointF(*point))
    return path


def _closed(*points: tuple[float, float]) -> QPainterPath:
    path = _lines(*points)
    path.closeSubpath()
    return path


def _circle(x: float, y: float, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QPointF(x, y), radius, radius)
    return path


def _rounded(left: float, top: float, right: float, bottom: float, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(QRectF(left, top, right - left, bottom - top), radius, radius)
    return path


def _star(x: float, y: float, size: float) -> QPainterPath:
    inner = size * .28
    return _closed((x, y - size), (x + inner, y - inner), (x + size, y), (x + inner, y + inner),
                   (x, y + size), (x - inner, y + inner), (x - size, y), (x - inner, y - inner))


def _arrow(start: tuple[float, float], end: tuple[float, float]) -> list[QPainterPath]:
    direction = 1 if end[0] > start[0] else -1
    head = end[0] - 4 * direction
    return [_lines(start, end), _lines((head, end[1] - 4), end, (head, end[1] + 4))]


def _refresh() -> list[QPainterPath]:
    arc = QPainterPath()
    arc.arcMoveTo(QRectF(4.5, 4.5, 15, 15), 60)
    arc.arcTo(QRectF(4.5, 4.5, 15, 15), 60, 280)
    return [arc, _lines((15.5, 3.5), (15.8, 6.4), (12.8, 7.2))]


def _person() -> list[QPainterPath]:
    shoulders = QPainterPath(QPointF(5, 20.5))
    shoulders.cubicTo(QPointF(5, 13.5), QPointF(19, 13.5), QPointF(19, 20.5))
    return [_circle(12, 8, 3.8), shoulders]


_SHAPES: dict[str, Callable[[], list[QPainterPath]]] = {
    "chart": lambda: [_rounded(3.5, 4.5, 20.5, 19.5, 2.5), _lines((11, 4.5), (11, 19.5)), _lines((11, 12), (20.5, 12))],
    "largest": lambda: [_lines((4, 7), (20, 7)), _lines((4, 12), (15, 12)), _lines((4, 17), (10, 17))],
    "search": lambda: [_circle(10.5, 10.5, 6), _lines((15, 15), (20, 20))],
    "cleanup": lambda: [_star(10, 13, 7), _star(18.5, 5.5, 2.8)],
    "types": lambda: [_circle(12, 12, 8.5), _lines((12, 3.5), (12, 12), (19.4, 16.2))],
    "age": lambda: [_circle(12, 12, 8.5), _lines((12, 7), (12, 12), (15.5, 14))],
    "changes": lambda: [*_arrow((4, 8), (19, 8)), *_arrow((20, 16), (5, 16))],
    "problems": lambda: [_closed((12, 3.8), (21, 19.8), (3, 19.8)), _lines((12, 9.5), (12, 14)),
                         _circle(12, 17, .4)],
    "users": _person,
    "folder": lambda: [_closed((3.5, 6.5), (9.5, 6.5), (11.5, 8.5), (20.5, 8.5), (20.5, 18.5), (3.5, 18.5))],
    "refresh": _refresh,
    "stop": lambda: [_rounded(6.5, 6.5, 17.5, 17.5, 2)],
    "help": lambda: [_circle(12, 12, 8.5), _question(), _circle(12, 16.6, .4)],
}


def _question() -> QPainterPath:
    path = QPainterPath(QPointF(9.4, 9.6))
    path.cubicTo(QPointF(9.4, 6.4), QPointF(14.8, 6.4), QPointF(14.6, 9.6))
    path.cubicTo(QPointF(14.4, 11.6), QPointF(12, 11.6), QPointF(12, 13.8))
    return path


NAMES = tuple(_SHAPES)


def icon(name: str, colour: QColor, disabled: QColor | None = None) -> QIcon:
    """The named line icon in ``colour`` (and ``disabled`` for the disabled state)."""
    strokes = _SHAPES[name]()
    result = QIcon()
    for mode, ink in ((QIcon.Mode.Normal, colour), (QIcon.Mode.Disabled, disabled or colour)):
        for size in _SIZES:
            result.addPixmap(_render(strokes, ink, size), mode)
    return result


def palette_icon(name: str, palette: QPalette) -> QIcon:
    """The named icon in the palette's text colour, muted when disabled."""
    return icon(name, palette.color(QPalette.ColorRole.WindowText),
                palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText))


def _render(strokes: list[QPainterPath], ink: QColor, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 24, size / 24)
    painter.setPen(QPen(ink, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for stroke in strokes:
        painter.drawPath(stroke)
    painter.end()
    return pixmap
