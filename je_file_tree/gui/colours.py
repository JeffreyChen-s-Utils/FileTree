"""Contrast-based chart label ink, independent of the window's background theme."""

from PySide6.QtGui import QColor

MIN_TEXT_CONTRAST = 4.5
_SRGB_LINEAR_BOUNDARY = 0.04045


def luminance(colour: QColor) -> float:
    """Relative sRGB luminance for an opaque colour."""
    channels = (colour.redF(), colour.greenF(), colour.blueF())
    linear = tuple(channel / 12.92 if channel <= _SRGB_LINEAR_BOUNDARY else ((channel + .055) / 1.055) ** 2.4
                   for channel in channels)
    return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]


def contrast(first: QColor, second: QColor) -> float:
    """Ratio between two opaque sRGB colours, from 1 to 21."""
    bright, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (bright + .05) / (dark + .05)


def readable_ink(background: QColor) -> QColor:
    """Choose the stronger of black/white text; flat opaque fills reach at least 4.5:1."""
    black, white = QColor('#000000'), QColor('#ffffff')
    return black if contrast(black, background) >= contrast(white, background) else white
