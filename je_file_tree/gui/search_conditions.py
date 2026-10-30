"""Readable, independently removable conditions derived from the active search."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from je_file_tree.core.formatting import format_size
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.search_ranges import MAX_BYTES


CONDITIONS = ("text", "min_size", "max_size", "changed", "category", "kind")


def descriptions(text: str, state: Mapping[str, Any], unit: str) -> dict[str, str]:
    """Describe active input without coercing malformed saved bounds into valid ones."""
    result = {"text": tr("search_condition_name", value=text)} if text else {}
    for key, label in (("min_size", "search_larger"), ("max_size", "search_smaller")):
        value = state.get(key)
        if value is not None:
            size = (format_size(value, unit) + " (" + format_size(value, "B") + ")"
                    if type(value) is int and 0 <= value <= MAX_BYTES else tr("search_range_invalid"))
            result[key] = tr("search_condition_value", label=tr(label), value=size)
    changed = state.get("changed", "any")
    if changed == "custom":
        result["changed"] = tr("search_condition_dates", start=_date_value(state.get("date_start")),
                               through=_date_value(state.get("date_through")))
    elif changed != "any":
        result["changed"] = tr("search_condition_value", label=tr("search_changed"),
                               value=tr(f"search_changed_{changed}"))
    if state.get("category") is not None:
        result["category"] = tr("search_condition_value", label=tr("search_type"),
                                value=tr(f"category_{state['category']}"))
    if state.get("kind", "any") != "any":
        result["kind"] = tr("search_condition_value", label=tr("search_show"),
                            value=tr(f"search_kind_{state['kind']}"))
    return result


def _date_value(value: Any) -> str:
    if value is None or value == "":
        return tr("search_no_limit")
    return value if isinstance(value, str) else tr("search_range_invalid")


class SearchConditions(QWidget):
    """Present current conditions; removal requests go back to the search owner."""

    remove_requested = Signal(str)
    reset_requested = Signal()
    edit_requested = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.scope = QLineEdit()
        self.scope.setReadOnly(True)
        self.reset = QPushButton()
        self.reset.clicked.connect(self.reset_requested)
        self.edit = QToolButton()
        self.edit.setCheckable(True)
        self.edit.toggled.connect(self.edit_requested)
        self.empty = QLabel()
        self.empty.setWordWrap(True)
        self.labels: dict[str, QLabel] = {}
        self.buttons: dict[str, QToolButton] = {}
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(4, 2, 4, 2)
        grid.setColumnStretch(0, 1)
        grid.addWidget(self.empty, 0, 0, 1, 2)
        for row, key in enumerate(CONDITIONS, 1):
            label, button = QLabel(), QToolButton()
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard |
                                          Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            button.clicked.connect(lambda _checked=False, key=key: self.remove_requested.emit(key))
            self.labels[key], self.buttons[key] = label, button
            grid.addWidget(label, row, 0)
            grid.addWidget(button, row, 1, Qt.AlignmentFlag.AlignTop)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setMaximumHeight(132)
        self.scroll.setMinimumHeight(132)
        self.scroll.setWidget(content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        scope_row = QHBoxLayout()
        scope_row.addWidget(self.scope, 1)
        scope_row.addWidget(self.edit)
        scope_row.addWidget(self.reset)
        layout.addLayout(scope_row)
        layout.addWidget(self.scroll)

    def update_conditions(self, text: str, state: Mapping[str, Any], root: Node | None, unit: str) -> None:
        """Redraw descriptions from the authoritative input and actual search root."""
        items = descriptions(text, state, unit)
        scope = (tr("search_scope_none") if root is None else
                 tr("search_scope_root", path=root.path) if root.path is not None else tr("search_scope_multi"))
        self.scope.setText(scope)
        self.scope.setCursorPosition(0)
        self.scope.setToolTip('<p>' + escape(scope) + '</p>')
        self.scope.setAccessibleName(tr("search_scope"))
        self.reset.setText(tr("search_clear_all"))
        self.edit.setText(tr("search_edit_conditions"))
        self.edit.setAccessibleName(tr("search_edit_conditions"))
        self.reset.setEnabled(root is not None and bool(items))
        self.empty.setText(tr("search_no_conditions"))
        self.empty.setVisible(not items)
        for key in CONDITIONS:
            label, button = self.labels[key], self.buttons[key]
            label.setText(items.get(key, ""))
            label.setToolTip('<p>' + escape(label.text()) + '</p>')
            label.setAccessibleName(label.text())
            button.setText('×')
            button.setAccessibleName(tr("search_remove_condition", condition=label.text()))
            button.setToolTip('<p>' + escape(button.accessibleName()) + '</p>')
            button.setEnabled(root is not None)
            label.setVisible(key in items)
            button.setVisible(key in items)
