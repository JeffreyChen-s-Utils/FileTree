"""The conditions under the Search tab's box: size, when last changed, file type, files or folders."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QWidget

from je_file_tree.core.analysis import CATEGORIES
from je_file_tree.core.formatting import format_size
from je_file_tree.core.search import ANY, KINDS
from je_file_tree.gui.i18n import tr

SIZE_STEPS = (1 << 20, 10 << 20, 100 << 20, 1 << 30, 10 << 30)
_DAY = 86400.0
CHANGED: dict[str, tuple[float | None, float | None]] = {  # key: (changed within, unchanged for), in seconds
    "any": (None, None),
    "week": (7 * _DAY, None),
    "month": (30 * _DAY, None),
    "year": (365 * _DAY, None),
    "stale_year": (None, 365 * _DAY),
    "stale_2y": (None, 730 * _DAY),
    "stale_5y": (None, 1826 * _DAY),
}


class SearchFilters(QWidget):
    """Five lists of conditions; ``changed`` is emitted whenever the user picks another one.

    ``state()`` and ``apply()`` give and take the choices as plain values (for saved filters);
    ``conditions()`` gives them as ``core.search.Query`` fields.
    """

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.min_size = QComboBox()
        self.max_size = QComboBox()
        self.changed_when = QComboBox()
        self.category = QComboBox()
        self.kind = QComboBox()
        self._labels = [QLabel() for _ in range(5)]
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        places = ((0, 0), (0, 2), (0, 4), (1, 0), (1, 2))
        for label, combo, (row, column) in zip(self._labels, self._combos(), places, strict=True):
            layout.addWidget(label, row, column)
            layout.addWidget(combo, row, column + 1)
            combo.currentIndexChanged.connect(lambda _index: self.changed.emit())
        layout.setColumnStretch(6, 1)
        self.retranslate()

    def conditions(self) -> dict[str, Any]:
        """The choices as ``Query`` fields."""
        changed_within, unchanged_for = CHANGED.get(self.changed_when.currentData(), (None, None))
        return {"min_size": self.min_size.currentData(), "max_size": self.max_size.currentData(),
                "changed_within": changed_within, "unchanged_for": unchanged_for,
                "category": self.category.currentData(), "kind": self.kind.currentData() or ANY}

    def state(self) -> dict[str, Any]:
        """The choices as plain values, to save."""
        return {"min_size": self.min_size.currentData(), "max_size": self.max_size.currentData(),
                "changed": self.changed_when.currentData(), "category": self.category.currentData(),
                "kind": self.kind.currentData()}

    def apply(self, state: Mapping[str, Any]) -> None:
        """Choose what ``state`` says; unknown or missing values fall back to *any*. Emits ``changed`` once."""
        values = (state.get("min_size"), state.get("max_size"), state.get("changed", "any"),
                  state.get("category"), state.get("kind", ANY))
        for combo, value in zip(self._combos(), values, strict=True):
            combo.blockSignals(True)
            position = combo.findData(value)
            combo.setCurrentIndex(position if position >= 0 else 0)
            combo.blockSignals(False)
        self.changed.emit()

    def retranslate(self) -> None:
        """Re-read every translated text, keeping the choices."""
        current = self.state()
        for label, key in zip(self._labels, ("search_larger", "search_smaller", "search_changed", "search_type",
                                             "search_show"), strict=True):
            label.setText(tr(key))
        sizes = [(tr("search_no_limit"), None)] + [(format_size(step), step) for step in SIZE_STEPS]
        _fill(self.min_size, sizes)
        _fill(self.max_size, sizes)
        _fill(self.changed_when, [(tr(f"search_changed_{key}"), key) for key in CHANGED])
        _fill(self.category, [(tr("search_type_any"), None)]
              + [(tr(f"category_{category}"), category) for category in CATEGORIES])
        _fill(self.kind, [(tr(f"search_kind_{kind}"), kind) for kind in KINDS])
        for combo, value in zip(self._combos(), current.values(), strict=True):
            combo.blockSignals(True)
            combo.setCurrentIndex(max(combo.findData(value), 0))
            combo.blockSignals(False)

    def _combos(self) -> tuple[QComboBox, ...]:
        return self.min_size, self.max_size, self.changed_when, self.category, self.kind


def _fill(combo: QComboBox, items: list[tuple[str, Any]]) -> None:
    combo.blockSignals(True)
    combo.clear()
    for text, data in items:
        combo.addItem(text, data)
    combo.blockSignals(False)
