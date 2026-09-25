"""The "How to use FileTree" window."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

from file_tree.gui.i18n import tr


class HelpDialog(QDialog):
    """Shows the help text of the current language."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("help_title"))
        self.resize(640, 560)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(tr("help_html"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(browser)
        layout.addWidget(buttons)
        self.browser = browser
