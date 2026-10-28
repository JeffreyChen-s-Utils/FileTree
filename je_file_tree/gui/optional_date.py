"""Optional ISO date input with an explicitly accepted calendar choice."""

from __future__ import annotations

from PySide6.QtCore import QDate, QLocale, Qt, Signal
from PySide6.QtWidgets import (
    QCalendarWidget, QDialog, QDialogButtonBox, QHBoxLayout, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from je_file_tree.gui.i18n import current_language, tr


class CalendarDialog(QDialog):
    """Choose a date without changing its caller until acceptance."""

    def __init__(self, text: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("date_choose"))
        self.calendar = QCalendarWidget()
        self.calendar.setLocale(QLocale(current_language().replace('-', '_')))
        parsed = QDate.fromString(text, "yyyy-MM-dd")
        self.calendar.setSelectedDate(parsed if parsed.isValid() else QDate.currentDate())
        self.calendar.activated.connect(lambda _date: self.accept())
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr('date_accept'))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('date_cancel'))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.calendar)
        layout.addWidget(self.buttons)
        self.calendar.ensurePolished()
        self.calendar.setMinimumSize(self.calendar.layout().sizeHint())
        self.calendar.setFocus()


class OptionalDateEdit(QWidget):
    """Keep blank or invalid text intact; a calendar only supplies an explicit choice."""

    text_changed = Signal(str)

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.edit = QLineEdit(text)
        self.edit.setMaxLength(128)
        self.clear_button = QPushButton()
        self.choose_button = QPushButton()
        for button in (self.clear_button, self.choose_button):
            button.setAutoDefault(False)
        self.clear_button.clicked.connect(self.clear)
        self.choose_button.clicked.connect(self.choose_date)
        self.edit.textChanged.connect(self.text_changed)
        self.dialog: CalendarDialog | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.choose_button)
        layout.addWidget(self.clear_button)
        self.setFocusProxy(self.edit)
        QWidget.setTabOrder(self.edit, self.choose_button)
        QWidget.setTabOrder(self.choose_button, self.clear_button)
        self.retranslate()

    def text(self) -> str:
        """Return literal input, including an empty or invalid date."""
        return self.edit.text()

    def setText(self, text: str) -> None:
        """Replace the draft without interpreting or correcting it."""
        self.edit.setText(text)

    def clear(self) -> None:
        """Remove a bound and return keyboard focus to the input."""
        self.edit.clear()
        self.edit.setFocus()

    def retranslate(self) -> None:
        """Translate controls while retaining the draft."""
        self.edit.setPlaceholderText(tr("search_date_format"))
        self.choose_button.setText(tr("date_choose"))
        self.clear_button.setText(tr("date_clear"))
        self.choose_button.setAccessibleName(tr("date_choose"))
        self.clear_button.setAccessibleName(tr("date_clear"))

    def choose_date(self) -> None:
        """Open one owned calendar; Cancel leaves the literal draft unchanged."""
        if self.dialog is not None:
            return
        dialog = CalendarDialog(self.text(), self)
        self.dialog = dialog
        if self.window().testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen):
            dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        dialog.finished.connect(lambda result: self._chosen(dialog, result))
        dialog.open()

    def _chosen(self, dialog: CalendarDialog, result: int) -> None:
        if result == QDialog.DialogCode.Accepted:
            self.setText(dialog.calendar.selectedDate().toString("yyyy-MM-dd"))
        self.dialog = None
        dialog.deleteLater()
        self.edit.setFocus()
