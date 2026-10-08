"""Serialize source-operation owners across independently scanned result tabs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from je_file_tree.gui.main_window import MainWindow


class OperationGroup:
    """GUI-thread ownership only; every tab retains its own workers and source revalidation."""

    def __init__(self) -> None:
        self.windows: list[MainWindow] = []
        self._refreshing = False

    @property
    def busy(self) -> bool:
        """An open source-operation review also blocks new mutations in every other tab."""
        return any(window.local_operation_busy for window in self.windows)

    def refresh(self, source: MainWindow) -> None:
        """Synchronize action availability without processing events or recursively refreshing peers."""
        if self._refreshing:
            return
        self._refreshing = True
        try:
            for window in self.windows:
                if window is not source and not window._closing:
                    window._update_actions()
        finally:
            self._refreshing = False
