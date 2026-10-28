"""Workspace folder budget editor and dated observation table."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from je_file_tree.gui.folder_budget_store import BudgetRow, FolderBudgetStore, display_error
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.search_ranges import UNITS, exact_bytes


class FolderBudgetDialog(QDialog):
    """Edit bounded rules without scanning sources or changing the current tree."""

    def __init__(self, store: FolderBudgetStore, parent=None, *, selected_path: str = "") -> None:
        super().__init__(parent)
        self.store = store
        self.selected_identity: str | None = None
        self.table = QTableWidget(0, 6, self)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._selection)
        self.name = QLineEdit()
        self.path = QLineEdit(selected_path)
        self.limit = QLineEdit()
        self.limit.setMaxLength(128)
        self.unit = QComboBox()
        self.unit.addItems(UNITS)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.add_button = QPushButton()
        self.update_button = QPushButton()
        self.delete_button = QPushButton()
        self.new_button = QPushButton()
        self.add_button.clicked.connect(self._add)
        self.update_button.clicked.connect(self._update)
        self.delete_button.clicked.connect(self._delete)
        self.new_button.clicked.connect(self._new)
        form = QFormLayout()
        self.name_label = QLabel()
        self.path_label = QLabel()
        self.limit_label = QLabel()
        form.addRow(self.name_label, self.name)
        form.addRow(self.path_label, self.path)
        capacity = QHBoxLayout()
        capacity.addWidget(self.limit)
        capacity.addWidget(self.unit)
        form.addRow(self.limit_label, capacity)
        buttons = QHBoxLayout()
        for button in (self.add_button, self.update_button, self.delete_button, self.new_button):
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addLayout(buttons)
        self.resize(990, 580)
        store.changed.connect(self.refresh)
        self.retranslate()

    def retranslate(self) -> None:
        """Translate all controls after an application language change."""
        self.setWindowTitle(tr("budget_title"))
        for label, key in ((self.name_label, "budget_name"), (self.path_label, "budget_path"),
                           (self.limit_label, "budget_limit")):
            label.setText(tr(key))
        self.table.setHorizontalHeaderLabels([tr("budget_name"), tr("budget_path"), tr("budget_limit"),
                                              tr("budget_usage"), tr("budget_excess"), tr("budget_status")])
        for button, key in ((self.add_button, "budget_add"), (self.update_button, "budget_update"),
                            (self.delete_button, "budget_delete"), (self.new_button, "budget_new")):
            button.setText(tr(key))
        self.refresh()

    def refresh(self) -> None:
        """Show the store's last persisted state and any read or write error."""
        self.table.setRowCount(len(self.store.rows))
        for index, row in enumerate(self.store.rows):
            fields = (row.rule.name, row.rule.path, str(row.rule.limit), self._usage(row),
                      self._excess(row), self._status(row))
            for column, value in enumerate(fields):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(index, column, item)
        for column, width in enumerate((110, 270, 80, 180, 90, 180)):
            self.table.setColumnWidth(column, width)
        self.error.setText(display_error(self.store.error))
        self.update_button.setEnabled(self.selected_identity is not None)
        self.delete_button.setEnabled(self.selected_identity is not None)

    def _usage(self, row: BudgetRow) -> str:
        observation = row.observation
        if observation is None:
            return tr("budget_waiting")
        when = datetime.fromtimestamp(observation.measured_at).strftime("%Y-%m-%d %H:%M")
        return tr("budget_dated_usage", usage=str(observation.bytes) if observation.bytes is not None else "?",
                  when=when)

    def _excess(self, row: BudgetRow) -> str:
        observation = row.observation
        if row.status not in ("over", "within") or observation is None or observation.bytes is None:
            return "?"
        return str(max(0, observation.bytes - row.rule.limit))

    def _status(self, row: BudgetRow) -> str:
        text = tr("budget_" + row.status)
        if row.status == "unknown" and row.observation is not None:
            text = tr("budget_unknown_reason", reason=tr("budget_reason_" + row.observation.reason))
        return tr("budget_alerted", status=text) if row.alerted else text

    def _selection(self) -> None:
        index = self.table.currentRow()
        if not 0 <= index < len(self.store.rows):
            return
        row = self.store.rows[index]
        self.selected_identity = row.rule.identity
        self.name.setText(row.rule.name)
        self.path.setText(row.rule.path)
        self.limit.setText(str(row.rule.limit))
        self.unit.setCurrentText("B")
        self.refresh()

    def _new(self) -> None:
        self.selected_identity = None
        self.table.clearSelection()
        self.name.clear()
        self.limit.clear()
        self.refresh()

    def _save(self, identity: str | None) -> None:
        try:
            limit = exact_bytes(self.limit.text(), self.unit.currentText())
            if limit is None:
                raise ValueError(tr("budget_invalid_limit"))
            self.store.put(self.name.text(), self.path.text(), limit, identity)
            self._new()
        except (OSError, ValueError) as error:
            self.error.setText(display_error(str(error)))

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
            self.error.setText(display_error(str(error)))
