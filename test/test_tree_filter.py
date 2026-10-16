"""Expanded-only filtering preserves model identities, live updates and cross-view selection."""

import time

from PySide6.QtCore import (
    QCoreApplication, QEvent, QItemSelection, QItemSelectionModel, QObject, QPersistentModelIndex, Qt,
)
from PySide6.QtWidgets import QTreeView
import pytest

from test_gui import window as window, _child, _scanned  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.node import Node
from je_file_tree.gui.tree_model import NAME, NODE_ROLE


def _wait(app, ready):
    deadline = time.monotonic() + 20
    while not ready():
        assert time.monotonic() < deadline, "filter timed out"
        app.processEvents()
        time.sleep(.005)
    app.processEvents()


def _setup(window, app, tmp_path):
    folder = tmp_path / "tree"
    for name in ("alpha", "beta"):
        child = folder / name
        child.mkdir(parents=True)
        (child / "NEEDLE 檔案.txt").write_bytes(b"payload")
        (child / "other.txt").write_bytes(b"other")
    _scanned(window, app, folder)
    results = window.results
    root = results.tree_model.root
    alpha, beta = _child(root, "alpha"), _child(root, "beta")
    results.tree.expand(results.tree_model.index_for(alpha))
    return results, root, alpha, beta


def _filter(results, app, text):
    controller = results.tree_filter
    controller.line.setText(text)
    _wait(app, lambda: not controller.timer.isActive() and not controller._workers
          and results.tree.model() is controller.proxy)


def test_only_expanded_contents_are_searched_and_totals_are_unchanged(window, qapp, tmp_path):
    results, root, alpha, beta = _setup(window, qapp, tmp_path)
    assert results.tree_filter.proxy.sourceModel() is None
    total = root.size
    results.tree.setColumnHidden(6, True)
    results.tree.setColumnWidth(0, 333)
    _filter(results, qapp, "needle")
    proxy = results.tree_filter.proxy
    assert proxy.sourceModel() is results.tree_model
    root_index = results.tree_filter.index_for(root)
    assert proxy.rowCount(root_index) == 1
    assert proxy.index(0, 0, root_index).data(NODE_ROLE) is alpha
    alpha_index = results.tree_filter.index_for(alpha)
    assert proxy.rowCount(alpha_index) == 1
    assert "NEEDLE" in proxy.index(0, 0, alpha_index).data()
    assert not results.tree_filter.index_for(beta).isValid()
    worker = results.tree_filter._current
    results.tree_model.set_unit("KB")
    results.tree_model.set_drive_total(10000)
    assert results.tree_filter._current is worker and not results.tree_filter.timer.isActive()
    assert proxy.rowCount(root_index) == 1
    assert root.size == total and results.outcome.result.root is root
    assert results.tree.isColumnHidden(6) and results.tree.columnWidth(0) == 333
    results.tree_filter.line.clear()
    assert results.tree.model() is results.tree_model
    assert proxy.sourceModel() is None
    assert results.tree.isExpanded(results.tree_model.index_for(alpha))
    assert results.tree_model.rowCount(results.tree_model.index_for(beta)) == 2


def test_filtered_selection_sorting_and_persistent_indices(window, qapp, tmp_path):
    results, _root, alpha, _beta = _setup(window, qapp, tmp_path)
    target = _child(alpha, "NEEDLE 檔案.txt")
    source = QPersistentModelIndex(results.tree_model.index_for(target))
    _filter(results, qapp, "needle")
    index = results.tree_filter.index_for(target)
    persistent = QPersistentModelIndex(index)
    flags = results.tree.selectionModel().SelectionFlag
    results.tree.selectionModel().setCurrentIndex(index, flags.ClearAndSelect | flags.Rows)
    assert results.selected_node() is target and results.selected_nodes() == [target]
    results.tree.sortByColumn(NAME, Qt.SortOrder.AscendingOrder)
    _wait(qapp, lambda: not results.tree_filter.timer.isActive() and not results.tree_filter._workers)
    assert source.data(NODE_ROLE) is target
    assert persistent.data(NODE_ROLE) is target
    assert results.selected_node() is target


@pytest.mark.parametrize("query", ["NEEDLE", "needle 檔案"])
def test_equivalent_filter_results_keep_mapping_selection_and_expansion(window, qapp, tmp_path, query):
    results, root, alpha, _beta = _setup(window, qapp, tmp_path)
    target = _child(alpha, "NEEDLE 檔案.txt")
    _filter(results, qapp, "needle")
    results.select_node(target)
    proxy, controller = results.tree_filter.proxy, results.tree_filter
    persistent = QPersistentModelIndex(controller.index_for(target))
    first_worker, first_allowed = controller._current, proxy.allowed
    layouts = []
    proxy.layoutChanged.connect(lambda *_args: layouts.append(True))
    _filter(results, qapp, query)
    assert controller._current is not first_worker and proxy.allowed == first_allowed
    assert not layouts, "equal accepted identities must not rebuild the proxy mapping"
    assert persistent.data(NODE_ROLE) is target
    assert results.selected_node() is target and results.selected_nodes() == [target]
    assert results.tree.isExpanded(controller.index_for(root))
    assert results.tree.isExpanded(controller.index_for(alpha))
    assert proxy.rowCount(controller.index_for(alpha)) == 1


def test_filter_worker_does_not_repeat_mapping_after_a_source_sort(window, qapp, tmp_path):
    results, _root, alpha, _beta = _setup(window, qapp, tmp_path)
    _filter(results, qapp, "needle")
    target = _child(alpha, "NEEDLE 檔案.txt")
    results.select_node(target)
    controller, proxy = results.tree_filter, results.tree_filter.proxy
    persistent = QPersistentModelIndex(controller.index_for(target))
    layouts = []
    proxy.layoutChanged.connect(lambda *_args: layouts.append(True))
    results.tree.sortByColumn(NAME, Qt.SortOrder.AscendingOrder)
    assert layouts, "the source sort still remaps the proxy normally"
    layouts.clear()
    _wait(qapp, lambda: not controller.timer.isActive() and not controller._workers)
    assert not layouts, "the worker must not repeat an already-applied source sort"
    assert persistent.data(NODE_ROLE) is target and results.selected_node() is target


def test_different_filter_identities_remap_even_with_the_same_match_count(window, qapp, tmp_path):
    results, _root, alpha, _beta = _setup(window, qapp, tmp_path)
    _filter(results, qapp, "needle")
    target, other = _child(alpha, "NEEDLE 檔案.txt"), _child(alpha, "other.txt")
    results.select_node(target)
    controller, proxy = results.tree_filter, results.tree_filter.proxy
    before = proxy.allowed
    persistent = QPersistentModelIndex(controller.index_for(target))
    layouts = []
    proxy.layoutChanged.connect(lambda *_args: layouts.append(True))
    _filter(results, qapp, "other")
    assert len(proxy.allowed) == len(before) and proxy.allowed != before and layouts
    assert not persistent.isValid() and not controller.index_for(target).isValid()
    assert target not in results.selected_nodes()
    assert proxy.index(0, 0, controller.index_for(alpha)).data(NODE_ROLE) is other


def test_live_refresh_with_unchanged_matches_keeps_updated_source_mapping(window, qapp, tmp_path):
    results, root, alpha, _beta = _setup(window, qapp, tmp_path)
    results.show_live_root(root)
    results.tree.expand(results.tree_model.index_for(alpha))
    _filter(results, qapp, "needle")
    target = _child(alpha, "NEEDLE 檔案.txt")
    results.select_node(target)
    controller, proxy, source = results.tree_filter, results.tree_filter.proxy, results.tree_model
    persistent = QPersistentModelIndex(controller.index_for(target))
    before = proxy.allowed
    # The appended row changes source membership and pushes the selected match to a different row.
    leaf = Node("unmatched arrival.txt", False, size=100, parent=alpha)
    alpha.children.append(leaf)
    layouts = []
    proxy.layoutChanged.connect(lambda *_args: layouts.append(True))
    source.refresh()
    assert layouts, "the source refresh must still rebuild changed source rows"
    layouts.clear()
    _wait(qapp, lambda: not controller.timer.isActive() and not controller._workers)
    assert proxy.allowed == before and not layouts
    assert source.rowCount(source.index_for(alpha)) == 3
    assert proxy.rowCount(controller.index_for(alpha)) == 1 and not controller.index_for(leaf).isValid()
    assert persistent.data(NODE_ROLE) is target and results.selected_node() is target
    mapped = proxy.mapToSource(persistent)
    assert mapped.row() == source.index_for(target).row() == 1


def test_cross_view_hidden_target_clears_filter_and_new_query_has_fresh_mapping(window, qapp, tmp_path):
    results, _root, _alpha, beta = _setup(window, qapp, tmp_path)
    _filter(results, qapp, "needle")
    results.select_node(_child(beta, "other.txt"))
    assert not results.tree_filter.line.text()
    assert results.selected_node().name == "other.txt"
    _filter(results, qapp, "other")
    assert results.tree_filter.index_for(_child(beta, "other.txt")).isValid()
    assert not results.tree_filter.index_for(_child(beta, "NEEDLE 檔案.txt")).isValid()


def test_live_refresh_and_branch_replacement_discard_old_filter_state(window, qapp, tmp_path):
    results, root, alpha, beta = _setup(window, qapp, tmp_path)
    results.show_live_root(root)
    results.tree.expand(results.tree_model.index_for(alpha))
    assert results.tree_model.live
    _filter(results, qapp, "needle")
    leaf = Node("another needle.txt", False, size=1, parent=alpha)
    alpha.children.append(leaf)
    results.tree_model.refresh()
    _wait(qapp, lambda: not results.tree_filter.timer.isActive() and not results.tree_filter._workers)
    assert results.tree_filter.index_for(leaf).isValid()
    other_source = QPersistentModelIndex(results.tree_model.index_for(beta))
    new = Node("alpha", True, children=[])
    results.tree_model.replace(alpha, new)
    _wait(qapp, lambda: not results.tree_filter.timer.isActive() and not results.tree_filter._workers)
    assert alpha not in results.tree_filter.expanded
    assert not results.tree_filter.index_for(leaf).isValid()
    assert other_source.data(NODE_ROLE) is beta
    assert results.tree_model.root is root
    results.tree_filter.line.clear()
    assert not results.tree_filter.index_for(leaf).isValid()


def test_close_joins_query_workers_and_rejects_queued_results(window, qapp, tmp_path):
    results, _root, _alpha, _beta = _setup(window, qapp, tmp_path)
    controller = results.tree_filter
    controller.line.setText("needle")
    controller.timer.stop()
    controller._start()
    worker = controller._current
    controller.shutdown()
    controller._ready(worker, frozenset())
    assert worker.cancel.is_set() and not worker.isRunning()
    assert results.tree.model() is results.tree_model


def test_repeated_filter_switches_retire_unused_tree_and_header_selection_models(window, qapp, tmp_path):
    results, _root, alpha, _beta = _setup(window, qapp, tmp_path)
    target = _child(alpha, "NEEDLE 檔案.txt")
    results.select_node(target)
    retired, destroyed = results.tree.selectionModel(), []
    retired.destroyed.connect(lambda: destroyed.append(True))
    for _cycle in range(5):
        _filter(results, qapp, "needle")
        assert results.selected_node() is target
        results.tree_filter.line.clear()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert results.selected_node() is target
        assert results.tree.header().selectionModel() is results.tree.selectionModel()
        assert len(results.tree.findChildren(QItemSelectionModel)) == 1
    assert destroyed == [True]
    assert (tmp_path / "tree" / "alpha" / "NEEDLE 檔案.txt").read_bytes() == b"payload"


def test_replaced_selection_detaches_and_suppresses_obsolete_callbacks_before_deferred_delete(window, qapp, tmp_path):
    results, root, alpha, _beta = _setup(window, qapp, tmp_path)
    results.select_node(_child(alpha, "NEEDLE 檔案.txt"))
    old = results.tree.selectionModel()
    notices, destroyed = [], []
    old.currentChanged.connect(lambda *_args: notices.append(True))
    old.selectionChanged.connect(lambda *_args: notices.append(True))
    old.destroyed.connect(lambda: destroyed.append(True))
    controller = results.tree_filter
    controller.proxy.allowed = frozenset(id(node) for node in root.iter_nodes())
    controller.proxy.setSourceModel(results.tree_model)
    controller._switch(True)
    assert old.model() is None and not notices and not destroyed
    results.tree_model.sort(NAME, Qt.SortOrder.AscendingOrder)
    assert not notices
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert destroyed == [True] and results.selected_node().name == "NEEDLE 檔案.txt"


@pytest.mark.parametrize("parented_to_tree", [False, True])
def test_switching_keeps_borrowed_selection_model_used_by_another_view(window, qapp, tmp_path, parented_to_tree):
    results, root, alpha, _beta = _setup(window, qapp, tmp_path)
    owner = QObject(window)
    shared = QItemSelectionModel(results.tree_model, results.tree if parented_to_tree else owner)
    other = QTreeView(window)
    other.setModel(results.tree_model)
    other.setSelectionModel(shared)
    results.tree.setSelectionModel(shared)
    target = _child(alpha, "NEEDLE 檔案.txt")
    shared.setCurrentIndex(results.tree_model.index_for(target), shared.SelectionFlag.ClearAndSelect
                           | shared.SelectionFlag.Rows)
    try:
        _filter(results, qapp, "needle")
        results.tree_filter.line.clear()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert shared.model() is results.tree_model and other.selectionModel() is shared
        assert shared.currentIndex().data(NODE_ROLE) is target
        assert shared.selectedRows()[0].data(NODE_ROLE) is target and target.is_in(root)
    finally:
        other.setModel(None)
        shared.setModel(None)
        shared.deleteLater()
        other.deleteLater()
        owner.deleteLater()


@pytest.mark.parametrize("descending", [False, True])
@pytest.mark.parametrize("sparse", [False, True])
def test_switch_compacts_adjacent_rows_without_widening_selection(qapp, descending, sparse):
    from je_file_tree.gui.tree_filter import TreeFilter
    from je_file_tree.gui.tree_model import FolderTreeModel

    root = Node("root", True, children=[])
    branches = [Node(name, True, children=[], parent=root) for name in ("alpha", "beta")]
    root.children.extend(branches)
    for branch in branches:
        branch.children.extend(Node(f"{row:02d}-{'omit' if row % 3 == 0 else 'keep'}", False,
                                    size=row, parent=branch) for row in range(12))
    source = FolderTreeModel()
    source.set_root(root)
    source.sort(NAME, Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder)
    tree = QTreeView()
    tree.setModel(source)
    controller = TreeFilter(tree, source, tree)
    try:
        for node in [root, *branches]:
            tree.expand(source.index_for(node))
        wanted = {root, branches[0], *(node for branch in branches for row, node in enumerate(branch.children)
                                      if not sparse or row % 4 != 0)}
        picked = QItemSelection()
        for node in reversed(list(wanted)):
            index = source.index_for(node)
            picked.select(index, index.siblingAtColumn(source.columnCount() - 1))
        tree.selectionModel().select(picked, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        current = branches[1]
        tree.selectionModel().setCurrentIndex(source.index_for(current), QItemSelectionModel.SelectionFlag.NoUpdate)
        controller.line.setText("keep")
        _wait(qapp, lambda: not controller.timer.isActive() and not controller._workers)
        wanted = {node for node in wanted if controller.index_for(node).isValid()}
        for filtered in (True, False):
            if not filtered:
                controller.line.clear()
            selection = tree.selectionModel()
            indexes = selection.selectedRows()
            assert {index.data(NODE_ROLE) for index in indexes} == wanted
            assert len(selection.selectedIndexes()) == len(wanted) * tree.model().columnCount()
            assert tree.currentIndex().data(NODE_ROLE) is current
            rows = {}
            for index in indexes:
                rows.setdefault(index.parent(), set()).add(index.row())
            runs = sum(sum(row - 1 not in group for row in group) for group in rows.values())
            assert len(selection.selection()) == runs
            assert all(part.left() == 0 and part.right() == source.columnCount() - 1
                       for part in selection.selection())
    finally:
        controller.shutdown()
        tree.close()


@pytest.mark.parametrize("filtered", [False, True])
def test_whole_row_switch_captures_nodes_without_per_cell_qt_expansion(qapp, monkeypatch, filtered):
    from je_file_tree.gui.tree_filter import TreeFilter
    from je_file_tree.gui.tree_model import FolderTreeModel

    root = Node("root", True, children=[])
    root.children.extend(Node(f"file-{row:04d}", False, size=500-row, parent=root) for row in range(500))
    source = FolderTreeModel()
    source.set_root(root)
    tree = QTreeView()
    tree.setModel(source)
    controller = TreeFilter(tree, source, tree)
    try:
        tree.expand(source.index_for(root))
        controller.proxy.allowed = frozenset(id(node) for node in root.children)
        controller.proxy.setSourceModel(source)
        if filtered:
            controller._switch(True)
        model = tree.model()
        parent = controller.index_for(root)
        picked = QItemSelection(model.index(20, 0, parent), model.index(479, model.columnCount()-1, parent))
        selection = tree.selectionModel()
        selection.select(picked, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        wanted = {index.data(NODE_ROLE) for index in selection.selectedRows()}

        def expanded_rows(*_args):
            raise AssertionError("whole-row capture expanded every selected cell through Qt")

        monkeypatch.setattr(selection, "selectedRows", expanded_rows)
        controller._switch(not filtered)
        assert {index.data(NODE_ROLE) for index in tree.selectionModel().selectedRows()} == wanted
        assert len(tree.selectionModel().selection()) == 1
    finally:
        controller.shutdown()
        tree.close()
