"""An extension's containing folders have disjoint recorded totals and bounded largest lists."""

import threading
from types import SimpleNamespace

from test_gui import _wait
from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.analysis import extension_of
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan
from je_file_tree.core.type_locations import type_locations
from je_file_tree.gui.scan_worker import analyse


def test_direct_folder_counts_do_not_overlap_and_top_limits_keep_full_denominator() -> None:
    root = Node('/root', True, children=[])
    folder = Node('nested', True, children=[], parent=root)
    root.children.extend([folder, Node('a.JPG', False, size=10, parent=root),
                          Node('skip.jpg', False, size=100, is_link=True, parent=root)])
    folder.children.extend([Node('b.jpg', False, size=20, parent=folder),
                            Node('c.jpg', False, size=30, parent=folder),
                            Node('d.mp4', False, size=80, parent=folder)])
    result = type_locations(root, lambda file: extension_of(file.name) == '.jpg', limit=1)
    assert result.total == 60
    assert [file.name for file in result.files] == ['c.jpg']
    assert [(row.folder, row.size, row.count) for row in result.folders] == [(folder, 50, 2)]
    result = type_locations(root, lambda file: extension_of(file.name) == '.jpg')
    assert sum(row.size for row in result.folders) == result.total == 60
    assert sum(row.count for row in result.folders) == 3
    cancel = threading.Event()
    cancel.set()
    assert type_locations(root, lambda _file: True, cancel=cancel) is None


def test_deep_empty_and_zero_size_matches_do_not_require_recursion() -> None:
    root = Node('/root', True, children=[])
    node = root
    for _ in range(1100):
        child = Node('d', True, children=[], parent=node)
        node.children.append(child)
        node = child
    node.children.append(Node('empty.jpg', False, size=0, parent=node))
    result = type_locations(root, lambda _file: True)
    assert result.total == 0 and len(result.files) == 1
    assert result.folders[0].count == 1 and result.folders[0].folder is node


def test_type_drill_down_and_folder_selection_follow_the_active_scan(window, qapp, sample_tree) -> None:
    window.results.show_outcome(analyse(scan(sample_tree)))
    results = window.results
    results.show_largest_of_type('.jpg')
    _wait(qapp, lambda: results._focus_worker is None)
    rows = results.type_locations_model.rows()
    assert len(rows) == 1 and rows[0].folder.name == 'photos' and rows[0].size == 200
    assert rows[0].count == 1 and results.type_locations_model.total == 200
    assert not results._type_locations_pane.isHidden()
    results.type_locations_table.doubleClicked.emit(results.type_locations_table.model().index(0, 0))
    assert results.selected_node() is rows[0].folder
    results.show_all_largest()
    assert results._type_locations_pane.isHidden() and results.type_locations_model.rowCount() == 0


def test_new_focus_discards_previous_reply_and_stop_joins_all_workers(window, qapp, sample_tree) -> None:
    window.results.show_outcome(analyse(scan(sample_tree)))
    results = window.results
    results.show_largest_of_type('.jpg')
    old = results._focus_worker
    results.show_largest_of_type('.py')
    assert old.cancel.is_set()
    matches = type_locations(results.outcome.result.root, lambda _file: True)
    results._focused_ready(SimpleNamespace(), matches)
    assert results.largest_model.rowCount() == 0
    _wait(qapp, lambda: results._focus_worker is None)
    assert [file.name for file in results.largest_model.rows()] == ['main.py']
    results.show_largest_of_type('.jpg')
    workers = list(results._list_workers)
    results.wait_for_lists()
    assert not any(worker.isRunning() for worker in workers)
