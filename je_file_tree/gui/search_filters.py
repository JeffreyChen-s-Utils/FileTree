"""The conditions under the Search tab's box: size, when last changed, file type, files or folders."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QPushButton, QSizePolicy, QWidget

from je_file_tree.core.analysis import CATEGORIES
from je_file_tree.core.formatting import format_size
from je_file_tree.core.search import ANY, KINDS
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.search_ranges import MAX_BYTES, SearchRangeDialog, calendar_bounds, validate_sizes

FILTER_PAIR_WIDTH = 250
MAX_FILTER_PAIRS = 3

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
        self._dates: dict[str, Any] = {}
        self.custom = QPushButton()
        self.custom.clicked.connect(self._edit_ranges)
        self.min_size = QComboBox()
        self.max_size = QComboBox()
        self.changed_when = QComboBox()
        self.category = QComboBox()
        self.kind = QComboBox()
        self._labels = [QLabel() for _ in range(5)]
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._columns = 0
        for label, combo in zip(self._labels, self._combos(), strict=True):
            label.setBuddy(combo)
            combo.setMinimumContentsLength(1)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            combo.currentIndexChanged.connect(lambda _index: self.changed.emit())
        self._arrange(MAX_FILTER_PAIRS)
        self.retranslate()

    def resizeEvent(self, event) -> None:
        """Keep filter inputs reachable as the result pane narrows."""
        super().resizeEvent(event)
        self._arrange(max(1, min(MAX_FILTER_PAIRS, self.width() // FILTER_PAIR_WIDTH)))

    def _arrange(self, columns: int) -> None:
        if columns == self._columns:
            return
        self._columns = columns
        for widget in (*self._labels, *self._combos(), self.custom):
            self._layout.removeWidget(widget)
        for column in range(MAX_FILTER_PAIRS * 2):
            self._layout.setColumnStretch(column, 0)
        for index, (label, combo) in enumerate(zip(self._labels, self._combos(), strict=True)):
            row, group = divmod(index, columns)
            self._layout.addWidget(label, row, group * 2)
            self._layout.addWidget(combo, row, group * 2 + 1)
            self._layout.setColumnStretch(group * 2 + 1, 1)
        row, group = divmod(len(self._labels), columns)
        self._layout.addWidget(self.custom, row, group * 2, 1, 2)

    def conditions(self) -> dict[str, Any]:
        """The choices as ``Query`` fields."""
        validate_sizes(self.min_size.currentData(), self.max_size.currentData())
        dates = {}
        if self.changed_when.currentData() == "custom":
            if not self._dates.get("date_start") and not self._dates.get("date_through"):
                raise ValueError(tr("search_range_date_error"))
            since, before = calendar_bounds(self._dates.get("date_start"), self._dates.get("date_through"))
            dates = {"modified_since": since, "modified_before": before}
        changed_within, unchanged_for = CHANGED.get(self.changed_when.currentData(), (None, None))
        return {"min_size": self.min_size.currentData(), "max_size": self.max_size.currentData(),
                "changed_within": changed_within, "unchanged_for": unchanged_for,
                "category": self.category.currentData(), "kind": self.kind.currentData() or ANY, **dates}

    def state(self) -> dict[str, Any]:
        """The choices as plain values, to save."""
        return {"min_size": self.min_size.currentData(), "max_size": self.max_size.currentData(),
                "changed": self.changed_when.currentData(), "category": self.category.currentData(),
                "kind": self.kind.currentData(),
                **(self._dates if self.changed_when.currentData() == "custom" else {})}

    def apply(self, state: Mapping[str, Any]) -> None:
        """Choose what ``state`` says; unknown or missing values fall back to *any*. Emits ``changed`` once."""
        self._dates = {key: state.get(key) for key in ("date_start", "date_through") if key in state}
        values = (state.get("min_size"), state.get("max_size"), state.get("changed", "any"),
                  state.get("category"), state.get("kind", ANY))
        for combo, value in zip(self._combos(), values, strict=True):
            combo.blockSignals(True)
            position = (self._custom_size(combo, value) if combo in (self.min_size, self.max_size)
                        else combo.findData(value))
            combo.setCurrentIndex(position if position >= 0 else 0)
            combo.blockSignals(False)
        self.changed.emit()

    def remove_condition(self, key: str) -> None:
        """Clear one filter through the same state application path as saved searches."""
        defaults = {"min_size": None, "max_size": None, "changed": "any", "category": None, "kind": ANY}
        if key not in defaults:
            return
        state = self.state()
        state[key] = defaults[key]
        if key == "changed":
            state.pop("date_start", None)
            state.pop("date_through", None)
        self.apply(state)

    def retranslate(self) -> None:
        """Re-read every translated text, keeping the choices."""
        current = self.state()
        self.custom.setText(tr("search_custom_ranges"))
        for label, key in zip(self._labels, ("search_larger", "search_smaller", "search_changed", "search_type",
                                             "search_show"), strict=True):
            label.setText(tr(key))
            label.buddy().setAccessibleName(tr(key))
        sizes = [(tr("search_no_limit"), None)] + [(format_size(step), step) for step in SIZE_STEPS]
        _fill(self.min_size, sizes)
        _fill(self.max_size, sizes)
        _fill(self.changed_when, [(tr(f"search_changed_{key}"), key) for key in (*CHANGED, "custom")])
        _fill(self.category, [(tr("search_type_any"), None)]
              + [(tr(f"category_{category}"), category) for category in CATEGORIES])
        _fill(self.kind, [(tr(f"search_kind_{kind}"), kind) for kind in KINDS])
        values = [current[key] for key in ("min_size", "max_size", "changed", "category", "kind")]
        for combo, value in zip(self._combos(), values, strict=True):
            combo.blockSignals(True)
            position = (self._custom_size(combo, value) if combo in (self.min_size, self.max_size)
                        else combo.findData(value))
            combo.setCurrentIndex(max(position, 0))
            combo.blockSignals(False)

    def _edit_ranges(self) -> None:
        state = self.state()
        dialog = SearchRangeDialog(state, self)
        result = dialog.exec()
        values = dialog.values
        dialog.deleteLater()
        if result != SearchRangeDialog.DialogCode.Accepted or values is None:
            return
        has_dates = bool(values["date_start"] or values["date_through"])
        changed = "custom" if has_dates else "any"
        self.apply({**state, **values, "changed": changed})

    @staticmethod
    def _custom_size(combo: QComboBox, value: Any) -> int:
        while combo.count() > len(SIZE_STEPS) + 1:
            combo.removeItem(combo.count() - 1)
        if value is not None and (type(value) is not int or value not in SIZE_STEPS):
            data = str(value) if type(value) is int and not 0 <= value <= MAX_BYTES else value
            combo.addItem(tr("search_exact_bytes", value=str(value)), data)
            return combo.count() - 1
        return combo.findData(value)

    def _combos(self) -> tuple[QComboBox, ...]:
        return self.min_size, self.max_size, self.changed_when, self.category, self.kind


def _fill(combo: QComboBox, items: list[tuple[str, Any]]) -> None:
    combo.blockSignals(True)
    combo.clear()
    for text, data in items:
        combo.addItem(text, data)
    combo.blockSignals(False)
