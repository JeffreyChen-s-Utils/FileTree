"""Filter only expanded folders, computing accepted node identities off the GUI thread."""

from __future__ import annotations

import threading

from PySide6.QtCore import QModelIndex, QObject, QSortFilterProxyModel, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import QLineEdit, QTreeView

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.tree_model import NODE_ROLE, FolderTreeModel


class ExpandedFilterWorker(QThread):
    """Inspect recorded children only below expanded folders, retaining matching ancestors."""

    ready = Signal(object)

    def __init__(self, root: Node, expanded: frozenset[Node], query: str, parent: QObject) -> None:
        super().__init__(parent)
        self.root, self.expanded, self.query = root, expanded, query.casefold()
        self.cancel = threading.Event()

    def run(self) -> None:
        """Compute accepted identities without calling any Qt model API on this thread."""
        accepted, stack = {id(self.root)}, [self.root]
        while stack:
            if self.cancel.is_set():
                return
            node = stack.pop()
            if node.is_dir:
                give_way()
            if self.query in node.name.casefold():
                ancestor = node
                while ancestor is not None and id(ancestor) not in accepted:
                    accepted.add(id(ancestor))
                    ancestor = ancestor.parent
            if node in self.expanded and not node.is_link:
                stack.extend(node.children)
        if not self.cancel.is_set():
            self.ready.emit(frozenset(accepted))


class ExpandedTreeProxy(QSortFilterProxyModel):
    """Constant-time membership filtering over the lazy source model; never recursive filtering."""

    def __init__(self, source: FolderTreeModel, parent: QObject) -> None:
        super().__init__(parent)
        self.allowed: frozenset[int] = frozenset()
        self.setSourceModel(source)

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:
        """Keep the root and worker-approved nodes without fetching descendants."""
        source = self.sourceModel()
        node = source.index(row, 0, parent).data(NODE_ROLE)
        return node is source.root or node is not None and id(node) in self.allowed

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Delegate numeric/name sorting to FolderTreeModel's persistent-index relayout."""
        self.sourceModel().sort(column, order)


class TreeFilter(QObject):
    """Own a debounced expanded-only query, source/proxy mapping and every cancellable worker."""

    selection_model_changed = Signal()

    def __init__(self, tree: QTreeView, source: FolderTreeModel, parent: QObject) -> None:
        super().__init__(parent)
        self.tree, self.source = tree, source
        self.line = QLineEdit()
        self.line.setClearButtonEnabled(True)
        self.proxy = ExpandedTreeProxy(source, self)
        self.expanded: set[Node] = set()
        self._workers: set[ExpandedFilterWorker] = set()
        self._current: ExpandedFilterWorker | None = None
        self._switching, self._closed = False, False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self._start)
        self.line.textChanged.connect(self._request)
        tree.expanded.connect(lambda index: self._expansion(index, True))
        tree.collapsed.connect(lambda index: self._expansion(index, False))
        source.modelReset.connect(self._reset)
        source.layoutChanged.connect(self._request)
        source.rowsRemoved.connect(self._request)
        source.rowsInserted.connect(self._request)
        self.retranslate()

    def retranslate(self) -> None:
        """Translate the query's placeholder, tooltip and accessible name."""
        self.line.setPlaceholderText(tr("tree_filter_placeholder"))
        self.line.setToolTip(tr("tree_filter_hint"))
        self.line.setAccessibleName(tr("tree_filter_placeholder"))

    def index_for(self, node: Node) -> QModelIndex:
        """Map a source index to whichever model the tree currently displays."""
        if self.source.root is None or not node.is_in(self.source.root):
            return QModelIndex()
        source = self.source.index_for(node)
        return self.proxy.mapFromSource(source) if self.tree.model() is self.proxy else source

    def reveal(self, node: Node) -> QModelIndex:
        """Clear a filter hiding a chart/list target before the normal cross-view selection."""
        index = self.index_for(node)
        if not index.isValid() and node.is_in(self.source.root):
            self.line.clear()
            index = self.index_for(node)
        return index

    def _expansion(self, index: QModelIndex, expanded: bool) -> None:
        if self._switching:
            return
        node = index.data(NODE_ROLE)
        if node is not None:
            if expanded:
                self.expanded.add(node)
            else:
                self.expanded.discard(node)
            self._request()

    def _reset(self) -> None:
        self.expanded.clear()
        self._request()

    def _request(self) -> None:
        if self._switching:
            return
        self.timer.stop()
        self._current = None
        for worker in self._workers:
            worker.cancel.set()
        if self._closed:
            return
        root = self.source.root
        self.expanded = {node for node in self.expanded if root is not None and node.is_in(root)}
        if not self.line.text():
            if self.tree.model() is self.proxy:
                self._switch(False)
        elif root is not None:
            self.timer.start()

    def _start(self) -> None:
        root = self.source.root
        if root is None or not self.line.text() or self._closed:
            return
        worker = ExpandedFilterWorker(root, frozenset(self.expanded), self.line.text(), self)
        self._current = worker
        self._workers.add(worker)
        worker.ready.connect(lambda allowed: self._ready(worker, allowed))
        worker.finished.connect(lambda: self._workers.discard(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _ready(self, worker: ExpandedFilterWorker, allowed: frozenset[int]) -> None:
        if self._closed or worker is not self._current or worker.cancel.is_set() or worker.root is not self.source.root:
            return
        self.proxy.allowed = allowed
        self.proxy.invalidate()
        if self.tree.model() is not self.proxy:
            self._switch(True)

    def _switch(self, filtered: bool) -> None:
        selected = [index.data(NODE_ROLE) for index in self.tree.selectionModel().selectedRows()]
        current = self.tree.currentIndex().data(NODE_ROLE)
        state = self.tree.header().saveState()
        self._switching = True
        try:
            self.tree.setModel(self.proxy if filtered else self.source)
            self.tree.header().restoreState(state)
            self.selection_model_changed.emit()
            for node in self.expanded:
                index = self.index_for(node)
                if index.isValid():
                    self.tree.expand(index)
            selection = self.tree.selectionModel()
            for node in selected:
                index = self.index_for(node)
                if index.isValid():
                    selection.select(index, selection.SelectionFlag.Select | selection.SelectionFlag.Rows)
            if current is not None:
                selection.setCurrentIndex(self.index_for(current), selection.SelectionFlag.NoUpdate)
        finally:
            self._switching = False

    def shutdown(self, *, wait: bool = True) -> None:
        """Invalidate late replies and join all workers before the main window closes."""
        self._closed = True
        self._request()
        if wait:
            for worker in self._workers.copy():
                wait_for(worker)
