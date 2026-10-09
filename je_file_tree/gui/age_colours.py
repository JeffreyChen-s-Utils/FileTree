"""Shared modified-age shades, with a distinct unknown colour for unusable dates."""

from __future__ import annotations

import math

from PySide6.QtGui import QColor

from je_file_tree.core.analysis import AGES, age_of
from je_file_tree.core.node import Node
from je_file_tree.gui.colours import readable_ink

AGE_COLOURS = dict(zip(AGES, ("#d7e9f4", "#aacfe2", "#7caac7", "#527fa4", "#315a80"), strict=True))
UNKNOWN_AGE_COLOUR = "#b9b9b9"


def age_colour(node: Node, now: float) -> QColor:
    """Shade a recorded modification date; absent, nonfinite or future dates are unknown."""
    if not math.isfinite(node.modified) or node.modified <= 0 or node.modified > now:
        return QColor(UNKNOWN_AGE_COLOUR)
    return QColor(AGE_COLOURS[age_of(node.modified, now)])


def age_text_colour(colour: QColor) -> QColor:
    """Keep chart labels readable across the light-to-dark age palette."""
    return readable_ink(colour)
