"""Literal captured names in the two existing source-move approval questions."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QWidget


def confirm_entry_move(parent: QWidget, title: str, text: str, *,
                       protected: bool = False) -> QMessageBox.StandardButton:
    """Ask Yes/No with literal text and preserve the ordinary/protected default-button choices."""
    icon = QMessageBox.Icon.Warning if protected else QMessageBox.Icon.Question
    dialog = QMessageBox(icon, title, "", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, parent)
    dialog.setTextFormat(Qt.TextFormat.PlainText)
    dialog.setText(text)
    if protected:
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
    try:
        return QMessageBox.StandardButton(dialog.exec())
    finally:
        dialog.deleteLater()
