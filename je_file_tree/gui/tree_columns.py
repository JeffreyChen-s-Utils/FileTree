"""A translated header menu with stable-key, validated column visibility settings."""

from __future__ import annotations

import json

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtWidgets import QMenu, QTreeView

from je_file_tree.gui.i18n import tr
from je_file_tree.gui.tree_model import (
    ACCESSED, ACCOUNTED_ALLOCATED, ACCOUNTED_SIZE, COLUMN_KEYS, CREATED, DRIVE_SHARE, NAME,
)

_SETTING = "tree_visible_columns"
_DEFAULT = [key for column, key in enumerate(COLUMN_KEYS)
            if column not in (DRIVE_SHARE, ACCESSED, CREATED, ACCOUNTED_SIZE, ACCOUNTED_ALLOCATED)]


class TreeColumns:
    """Remember visible optional columns; the name always remains available for navigation."""

    def __init__(self, tree: QTreeView, settings: QSettings | None = None) -> None:
        self.tree, self.settings = tree, settings
        visible = _DEFAULT
        if settings is not None:
            try:
                stored = json.loads(str(settings.value(_SETTING, "null")))
            except (ValueError, RecursionError):
                stored = None  # Invalid local preferences use the default layout.
            if isinstance(stored, list) and all(isinstance(key, str) and key in COLUMN_KEYS for key in stored):
                visible = stored
        self._apply(visible)
        header = tree.header()
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_menu)

    def menu(self) -> QMenu:
        """Build current translated choices, including a reset to the default columns."""
        menu = QMenu(self.tree)
        for column, key in enumerate(COLUMN_KEYS):
            action = menu.addAction(tr(key))
            action.setCheckable(True)
            action.setChecked(not self.tree.isColumnHidden(column))
            action.setEnabled(column != NAME)
            action.toggled.connect(lambda checked, number=column: self.set_visible(number, checked))
        menu.addSeparator()
        menu.addAction(tr("columns_reset"), self.reset)
        return menu

    def show_menu(self, point: QPoint) -> None:
        """Open the chooser at the header's requested screen position."""
        menu = self.menu()
        menu.exec(self.tree.header().mapToGlobal(point))
        menu.deleteLater()

    def set_visible(self, column: int, visible: bool) -> None:
        """Change one optional column and persist its stable translation key."""
        if 0 < column < len(COLUMN_KEYS):
            self.tree.setColumnHidden(column, not visible)
            self._save()

    def reset(self) -> None:
        """Restore the default columns and a readable name width."""
        self._apply(_DEFAULT)
        self.tree.setColumnWidth(NAME, 250)
        self._save()

    def _apply(self, visible: list[str]) -> None:
        for column, key in enumerate(COLUMN_KEYS):
            self.tree.setColumnHidden(column, column != NAME and key not in visible)

    def _save(self) -> None:
        if self.settings is not None:
            self.settings.setValue(_SETTING, json.dumps(
                [key for column, key in enumerate(COLUMN_KEYS) if not self.tree.isColumnHidden(column)]))
