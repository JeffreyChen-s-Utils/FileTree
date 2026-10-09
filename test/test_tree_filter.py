"""Expanded-only filtering preserves model identities, live updates and cross-view selection."""

import time

from PySide6.QtCore import QPersistentModelIndex, Qt

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
    total = root.size
    results.tree.setColumnHidden(6, True)
    results.tree.setColumnWidth(0, 333)
    _filter(results, qapp, "needle")
    proxy = results.tree_filter.proxy
    root_index = results.tree_filter.index_for(root)
    assert proxy.rowCount(root_index) == 1
    assert proxy.index(0, 0, root_index).data(NODE_ROLE) is alpha
    alpha_index = results.tree_filter.index_for(alpha)
    assert proxy.rowCount(alpha_index) == 1
    assert "NEEDLE" in proxy.index(0, 0, alpha_index).data()
    assert not results.tree_filter.index_for(beta).isValid()
    assert root.size == total and results.outcome.result.root is root
    assert results.tree.isColumnHidden(6) and results.tree.columnWidth(0) == 333
    results.tree_filter.line.clear()
    assert results.tree.model() is results.tree_model
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
