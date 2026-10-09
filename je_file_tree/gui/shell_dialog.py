"""Edit Explorer registration explicitly; opening this dialog never changes the registry."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QMessageBox, QVBoxLayout, QWidget

from je_file_tree.gui import shell_integration
from je_file_tree.gui.i18n import tr


class ShellIntegrationDialog(QDialog):
    """Apply a current-user Explorer folder verb only after Save."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("action_shell_integration"))
        self.enabled = QCheckBox(tr("shell_enabled"))
        self._readable = True
        try:
            self.enabled.setChecked(shell_integration.installed())
        except OSError as error:
            self._readable = False
            QMessageBox.warning(self, self.windowTitle(), tr("shell_failed", reason=str(error)))
        self.enabled.setEnabled(self._readable)
        hint = QLabel(tr("shell_hint"))
        hint.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(self._readable)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.enabled)
        layout.addWidget(hint)
        layout.addWidget(self.buttons)
        self.resize(520, 180)

    def accept(self) -> None:
        """Persist the actual registry state; a failed application keeps the dialog open."""
        if not self._readable:
            return
        try:
            shell_integration.set_enabled(self.enabled.isChecked(), tr("shell_scan"))
        except OSError as error:
            QMessageBox.warning(self, self.windowTitle(), tr("shell_failed", reason=str(error)))
            return
        super().accept()
