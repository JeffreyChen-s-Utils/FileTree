"""Filter only expanded folders, computing accepted node identities off the GUI thread."""

from __future__ import annotations

import threading

from PySide6.QtCore import (
    QItemSelection, QItemSelectionModel, QModelIndex, QObject, QSortFilterProxyModel, QThread, QTimer, Qt, Signal,
)
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

    def __init__(self, source: FolderTreeModel | None, parent: QObject) -> None:
        super().__init__(parent)
        self.allowed: frozenset[int] = frozenset()
        self.searched: frozenset[Node] | None = None
        # Membership comes from the owned worker; display-only changes must not recheck every row.
        self.setDynamicSortFilter(False)
        self.setSourceModel(source)

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:
        """Keep the root and worker-approved nodes without fetching descendants."""
        source = self.sourceModel()
        if source is None:
            return False
        # Native 100k-row entry: 1.93 s -> 1.65–1.76 s without per-row Qt index/data dispatch (2026-10-16).
        node = source.node_at(row, parent)
        return node is not None and (node is source.root or id(node) in self.allowed)

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:  # noqa: B008
        """Avoid mapping unsearched groups and physical files whose only children are virtual previews."""
        source = self.sourceModel()
        if source is None:
            return False
        if self.searched is not None and parent.isValid():
            index = self.mapToSource(parent)
            node = source.node(index)
            if node is None:
                return False
            # An expanded archive still has no scanned children; preview members never match.
            # Native 100k-member query: 403–411 ms -> 173–185 ms without their mapping (2026-10-16).
            if node not in self.searched or (not node.is_dir and not node.children):
                return source.canFetchMore(index)
        return super().hasChildren(parent)

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Delegate numeric/name sorting to FolderTreeModel's persistent-index relayout."""
        source = self.sourceModel()
        if source is not None:
            source.sort(column, order)


class TreeFilter(QObject):
    """Own a debounced expanded-only query, source/proxy mapping and every cancellable worker."""

    selection_model_changed = Signal()

    def __init__(self, tree: QTreeView, source: FolderTreeModel, parent: QObject) -> None:
        super().__init__(parent)
        self.tree, self.source = tree, source
        self._owned_selections = self._view_selections()
        self.line = QLineEdit()
        self.line.setClearButtonEnabled(True)
        self.proxy = ExpandedTreeProxy(None, self)
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
        self._release_selections()

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
        if self.proxy.searched is not None:
            self.proxy.searched = frozenset()
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
        changed = self.proxy.allowed != allowed
        self.proxy.searched = worker.expanded
        self.proxy.allowed = allowed
        if self.proxy.sourceModel() is None:
            self.proxy.setSourceModel(self.source)
        elif changed:
            # Equal-result queries: 100k rows / 1k selected took 2.7 s vs 0.23 s without
            # rebuilding the same mapping (native Windows, 2026-10-16).
            self.proxy.invalidate()
        if self.tree.model() is not self.proxy:
            self._switch(True)

    def _switch(self, filtered: bool) -> None:
        selected = [node for index in self.tree.selectionModel().selectedRows()
                    if isinstance(node := index.data(NODE_ROLE), Node)]
        current = self.tree.currentIndex().data(NODE_ROLE)
        state = self.tree.header().saveState()
        self._switching = True
        try:
            # Qt requests the same sort twice while rebinding. 100k rows / 1k selected:
            # clearing took 1.8 s vs 0.7 s without these redundant relayouts (Windows, 2026-10-16).
            with self.source.preserve_sort():
                before = self._view_selections()
                self.tree.setModel(self.proxy if filtered else self.source)
                self._owned_selections.update(self._view_selections() - before)
                self._release_selections()
                self.tree.header().restoreState(state)
            self.selection_model_changed.emit()
            for node in self.expanded:
                index = self.index_for(node)
                if index.isValid():
                    self.tree.expand(index)
            selection = self.tree.selectionModel()
            picked = QItemSelection()
            last_column = self.tree.model().columnCount() - 1
            for source in self.source.indexes_for(selected):
                index = self.proxy.mapFromSource(source) if filtered else source
                if index.isValid():
                    picked.select(index, index.siblingAtColumn(last_column))
            # 100k records / 1k selected took 3.6–4.2 s with individual lookup/selection (2026-10-16).
            if not picked.isEmpty():
                selection.select(picked, selection.SelectionFlag.Select)
            if current is not None:
                selection.setCurrentIndex(self.index_for(current), selection.SelectionFlag.NoUpdate)
            if not filtered:
                self.proxy.setSourceModel(None)
                self.proxy.searched = None
        finally:
            self._switching = False

    def _view_selections(self) -> set[QItemSelectionModel]:
        return {selection for owner in (self.tree, self.tree.header())
                for selection in owner.findChildren(QItemSelectionModel,
                                                    options=Qt.FindChildOption.FindDirectChildrenOnly)}

    def _release_selections(self) -> None:
        """Retire only our replaced view/header models; borrowed and active shared selections stay alive."""
        active = {self.tree.selectionModel(), self.tree.header().selectionModel()}
        # Native cycling: 2 -> 22 models after five filter/clear cycles (2026-10-16).
        # Qt retains replaced models; detach retired listeners now, delete after their event returns.
        for selection in self._owned_selections - active:
            self._owned_selections.remove(selection)
            selection.blockSignals(True)
            selection.setModel(None)
            selection.deleteLater()

    def shutdown(self, *, wait: bool = True) -> None:
        """Invalidate late replies and join all workers before the main window closes."""
        self._closed = True
        self._request()
        if wait:
            for worker in self._workers.copy():
                wait_for(worker)
