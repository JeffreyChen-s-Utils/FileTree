"""Workspace folder budget editor and dated observation table."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from je_file_tree.core.folder_budgets import budget_path
from je_file_tree.core.formatting import SIZE_UNITS, format_size
from je_file_tree.gui.folder_budget_store import (
    MAX_NAME, MAX_PATH, BudgetRow, FolderBudgetStore, display_error,
)
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.search_ranges import UNITS, editable_size, exact_bytes

BudgetFilter = Literal["all", "over", "unknown"]


class FolderBudgetDialog(QDialog):
    """Edit bounded rules without scanning sources or changing the current tree."""

    def __init__(self, store: FolderBudgetStore, parent: QWidget | None = None, *,
                 selected_path: str = "", unit: str = "auto", status_filter: BudgetFilter = "all") -> None:
        super().__init__(parent)
        self.store = store
        self._display_unit = unit
        self.selected_identity: str | None = None
        self.table = QTableWidget(0, 7, self)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setTabKeyNavigation(False)
        self.table.itemSelectionChanged.connect(self._selection)
        self.status_filter = QComboBox()
        for value in ("all", "over", "unknown"):
            self.status_filter.addItem("", value)
        self.status_filter.currentIndexChanged.connect(self._apply_filter)
        self.name, self.path, self.limit = QLineEdit(), QLineEdit(), QLineEdit()
        self.name.setMaxLength(MAX_NAME)
        self.path.setMaxLength(MAX_PATH)
        self.limit.setMaxLength(128)
        self.unit = QComboBox()
        self.unit.addItems(UNITS)
        self.error, self.empty_hint, self.hint, self.selection_hint = (QLabel() for _ in range(4))
        for label in (self.error, self.empty_hint, self.hint, self.selection_hint):
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
        self.add_button, self.update_button = QPushButton(), QPushButton()
        self.delete_button, self.new_button, self.choose_button = (QPushButton() for _ in range(3))
        for button, slot in ((self.add_button, self._add), (self.update_button, self._update),
                             (self.delete_button, self._delete), (self.new_button, self._new),
                             (self.choose_button, self._choose_folder)):
            button.setAutoDefault(False)
            button.clicked.connect(slot)
        self._build()
        self._clean_input = self._input()
        self.resize(990, 620)
        store.changed.connect(self.refresh)
        self.retranslate()
        self.set_filter(status_filter)
        if selected_path:
            self.select_path(selected_path)

    def _build(self) -> None:
        self.name_label, self.path_label, self.limit_label = (QLabel() for _ in range(3))
        for label, field in ((self.name_label, self.name), (self.path_label, self.path),
                             (self.limit_label, self.limit)):
            label.setBuddy(field)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.addRow(self.name_label, self.name)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path, 1)
        path_row.addWidget(self.choose_button)
        form.addRow(self.path_label, path_row)
        capacity = QHBoxLayout()
        capacity.addWidget(self.limit, 1)
        capacity.addWidget(self.unit)
        form.addRow(self.limit_label, capacity)
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.addWidget(self.selection_hint)
        editor_layout.addLayout(form)
        editor_layout.addWidget(self.hint)
        editor_layout.addWidget(self.error)
        self.editor_scroll = QScrollArea()
        self.editor_scroll.setWidgetResizable(True)
        self.editor_scroll.setWidget(editor)
        self.editor_scroll.setMinimumHeight(145)
        buttons = QHBoxLayout()
        for button in (self.new_button, self.add_button, self.update_button, self.delete_button):
            buttons.addWidget(button)
        self.close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.close_buttons.rejected.connect(self.reject)
        buttons.addWidget(self.close_buttons)
        layout = QVBoxLayout(self)
        self.filter_label = QLabel()
        self.filter_label.setBuddy(self.status_filter)
        filters = QHBoxLayout()
        filters.addWidget(self.filter_label)
        filters.addWidget(self.status_filter, 1)
        layout.addLayout(filters)
        layout.addWidget(self.empty_hint)
        layout.addWidget(self.table, 3)
        layout.addWidget(self.editor_scroll, 2)
        layout.addLayout(buttons)
        fields = (self.status_filter, self.table, self.name, self.path, self.choose_button, self.limit, self.unit,
                  self.new_button, self.add_button, self.update_button, self.delete_button,
                  self.close_buttons.button(QDialogButtonBox.StandardButton.Close))
        for before, after in zip(fields, fields[1:], strict=False):
            QWidget.setTabOrder(before, after)
        for column, width in enumerate((95, 135, 110, 110, 135, 100, 220)):
            self.table.setColumnWidth(column, width)

    def retranslate(self) -> None:
        """Translate controls and observations without replacing the edited input."""
        self.setWindowTitle(tr("budget_title"))
        self.filter_label.setText(tr("budget_filter"))
        self.status_filter.setAccessibleName(tr("budget_filter"))
        for index in range(self.status_filter.count()):
            self.status_filter.setItemText(index, tr("budget_filter_" + self.status_filter.itemData(index)))
        for label, field, key in ((self.name_label, self.name, "budget_name"),
                                  (self.path_label, self.path, "budget_path"),
                                  (self.limit_label, self.limit, "budget_limit")):
            label.setText(tr(key))
            field.setAccessibleName(tr(key))
        self.table.setHorizontalHeaderLabels([tr(key) for key in (
            "budget_name", "budget_path", "budget_limit", "budget_usage", "budget_observed",
            "budget_excess", "budget_status")])
        self.table.setAccessibleName(tr("budget_title"))
        self.unit.setAccessibleName(tr("budget_input_unit"))
        self.close_buttons.button(QDialogButtonBox.StandardButton.Close).setText(tr("budget_close"))
        for button, key in ((self.add_button, "budget_add"), (self.update_button, "budget_update"),
                            (self.delete_button, "budget_delete"), (self.new_button, "budget_new"),
                            (self.choose_button, "budget_choose")):
            button.setText(tr(key))
        self.empty_hint.setText(tr("budget_empty"))
        self.hint.setText(tr("budget_edit_hint"))
        self.refresh()

    def set_unit(self, unit: str) -> None:
        """Change observation display units while preserving exact, unsubmitted input."""
        self._display_unit = unit
        self.refresh()

    def select_path(self, path: str) -> None:
        """Locate a normalized existing identity, guarding unsubmitted edits before changing context."""
        if self._input() != self._clean_input:
            self.error.setText(tr("budget_keep_draft"))
            return
        try:
            normalized = budget_path(path)
        except ValueError as error:
            self.error.setText(display_error(str(error)))
            return
        self.set_filter("all")
        for index, row in enumerate(self.store.rows):
            if budget_path(row.rule.path) == normalized:
                self.table.selectRow(index)
                self._selection()
                self.table.scrollToItem(self.table.item(index, 0))
                self.name.setFocus()
                return
        self._new()
        self.path.setText(path)
        self._clean_input = self._input()
        self.path.setFocus()

    def set_filter(self, status_filter: BudgetFilter) -> None:
        """Change only the temporary visible row set, retaining identity and the editor draft."""
        index = self.status_filter.findData(status_filter)
        if index < 0:
            raise ValueError("Unknown budget filter")
        self.status_filter.setCurrentIndex(index)
        self._apply_filter()

    def _apply_filter(self) -> None:
        chosen = self.status_filter.currentData()
        visible = 0
        selected = None
        with QSignalBlocker(self.table):
            for index, row in enumerate(self.store.rows):
                matches = (chosen in ("all", row.status)
                           or chosen == "unknown" and row.status == "waiting")
                self.table.setRowHidden(index, not matches)
                visible += matches
                if row.rule.identity == self.selected_identity:
                    selected = (row, matches)
        self.empty_hint.setText(tr("budget_empty" if not self.store.rows else "budget_filter_empty"))
        self.empty_hint.setVisible(not visible)
        if selected is not None and not selected[1]:
            self.selection_hint.setText(tr("budget_editing_hidden", name=selected[0].rule.name,
                                           status=self._status(selected[0])))
        else:
            self.selection_hint.setText(tr("budget_editing") if self.selected_identity else tr("budget_creating"))

    def refresh(self) -> None:
        """Refresh persisted observations, preserving selection and editor contents."""
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(self.store.rows))
            self.table.clearSelection()
            selected = None
            for index, row in enumerate(self.store.rows):
                self._fill_row(index, row)
                if row.rule.identity == self.selected_identity:
                    selected = index
            if selected is not None:
                self.table.selectRow(selected)
            else:
                self.table.setCurrentCell(-1, -1)
            self.table.resizeRowsToContents()
        if self.store.error:
            self.error.setText(display_error(self.store.error))
        self.update_button.setEnabled(selected is not None)
        self.delete_button.setEnabled(selected is not None)
        self._apply_filter()

    def _fill_row(self, index: int, row: BudgetRow) -> None:
        observation = row.observation
        usage = observation.bytes if observation is not None else None
        excess = (max(0, usage - row.rule.limit) if usage is not None
                  and row.status in ("over", "within") else None)
        when = (datetime.fromtimestamp(observation.measured_at).strftime("%Y-%m-%d %H:%M")
                if observation is not None else tr("budget_not_scanned"))
        fields = (row.rule.name, row.rule.path, self._size(row.rule.limit), self._size(usage), when,
                  self._size(excess), self._status(row))
        precise = {2: row.rule.limit, 3: usage, 5: excess}
        for column, value in enumerate(fields):
            item = QTableWidgetItem(value)
            item.setData(Qt.ItemDataRole.UserRole, row.rule.identity)
            amount = precise.get(column)
            tip = tr("budget_exact", value=format_size(amount, "B")) if amount is not None else value
            item.setToolTip(tip)
            item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, tip)
            self.table.setItem(index, column, item)

    def _size(self, value: int | None) -> str:
        if value is None:
            return tr("budget_unknown")
        try:
            return format_size(value, self._display_unit)
        except OverflowError:
            power = len(SIZE_UNITS) - 1 if self._display_unit == "auto" else SIZE_UNITS.index(self._display_unit)
            divisor = 1024 ** power
            tenths, remainder = divmod(value * 10, divisor)
            if remainder * 2 > divisor or remainder * 2 == divisor and tenths % 2:
                tenths += 1
            whole, fraction = divmod(tenths, 10)
            return f"{whole:,}.{fraction} {SIZE_UNITS[power]}"

    def _status(self, row: BudgetRow) -> str:
        if row.observation is None:
            text = tr("budget_not_scanned")
        elif row.observation.version != row.rule.version:
            text = tr("budget_changed_limit")
        elif row.status == "unknown":
            text = tr("budget_unknown_reason", reason=tr("budget_reason_" + row.observation.reason))
        else:
            text = tr("budget_" + row.status)
        return tr("budget_alerted", status=text) if row.alerted else text

    def _selection(self) -> None:
        item = self.table.currentItem()
        if item is None or not self.table.selectedItems():
            return
        identity = item.data(Qt.ItemDataRole.UserRole)
        row = next((row for row in self.store.rows if row.rule.identity == identity), None)
        if row is None:
            return
        self.selected_identity = identity
        self.name.setText(row.rule.name)
        self.path.setText(row.rule.path)
        value, unit = editable_size(row.rule.limit, self._display_unit)
        self.limit.setText(value)
        self.unit.setCurrentText(unit)
        self._clean_input = self._input()
        self.error.clear()
        self.refresh()

    def _input(self) -> tuple[str, str, str, str]:
        return self.name.text(), self.path.text(), self.limit.text(), self.unit.currentText()

    def _new(self) -> None:
        self.selected_identity = None
        with QSignalBlocker(self.table):
            self.table.clearSelection()
            self.table.setCurrentCell(-1, -1)
        self.name.clear()
        self.limit.clear()
        self.error.clear()
        self._clean_input = self._input()
        self.refresh()
        self.name.setFocus()

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("budget_choose"), self.path.text())
        if path:
            self.path.setText(path)
            self.path.setFocus()

    def _fail(self, message: str, field: QWidget) -> None:
        self.error.setText(message)
        field.setFocus()
        self.editor_scroll.ensureWidgetVisible(field)
        if isinstance(field, QLineEdit):
            field.selectAll()

    def _validated_limit(self) -> int | None:
        if not self.name.text().strip():
            self._fail(tr("budget_invalid_name"), self.name)
            return None
        try:
            budget_path(self.path.text())
        except ValueError as error:
            self._fail(display_error(str(error)), self.path)
            return None
        try:
            limit = exact_bytes(self.limit.text(), self.unit.currentText())
            if limit is None:
                raise ValueError(tr("budget_invalid_limit"))
            return limit
        except ValueError as error:
            self._fail(str(error), self.limit)
            return None

    def _save(self, identity: str | None) -> None:
        limit = self._validated_limit()
        if limit is None:
            return
        try:
            self.store.put(self.name.text(), self.path.text(), limit, identity)
            self._new()
        except (OSError, ValueError) as error:
            field = self.path if "path" in str(error).lower() else self.name
            self._fail(display_error(str(error)), field)

    def _add(self) -> None:
        self._save(None)

    def _update(self) -> None:
        if self.selected_identity is not None:
            self._save(self.selected_identity)

    def _delete(self) -> None:
        if self.selected_identity is None:
            return
        try:
            self.store.delete(self.selected_identity)
            self._new()
        except (OSError, ValueError) as error:
            self._fail(display_error(str(error)), self.table)
