"""The detail pane computes bounded recorded totals and rejects cancelled/stale replies."""

import threading
from types import SimpleNamespace

from PySide6.QtCore import QSettings

from test_gui import _wait
from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.details import breakdown
from je_file_tree.core.formatting import format_size
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan
from je_file_tree.gui.details_panel import DetailsPanel
from je_file_tree.gui.scan_worker import analyse


def test_breakdown_counts_files_not_links_and_separates_unknown_dates() -> None:
    root = Node('/root', True, children=[])
    root.children.extend(Node(name, False, size=10, modified=modified, parent=root) for name, modified in
                         (('a.jpg', 999), ('b.mp4', 0), ('c.py', float('nan')), ('d.txt', 2000)))
    root.children.append(Node('ignored.jpg', False, size=200, is_link=True, parent=root))
    result = breakdown(root, 1000)
    assert result.types['images'] == (10, 1)
    assert sum(size for size, _ in result.types.values()) == 40
    assert result.ages['month'] == (10, 1) and result.ages['unknown'] == (30, 3)
    cancel = threading.Event()
    cancel.set()
    assert breakdown(root, 1000, cancel) is None


def test_breakdown_handles_deep_folders_without_recursion() -> None:
    root = Node('/root', True, children=[])
    node = root
    for _ in range(1100):
        child = Node('child', True, children=[], parent=node)
        node.children.append(child)
        node = child
    node.children.append(Node('test.txt', False, size=42, parent=node))
    assert breakdown(root, 1000).types['documents'] == (42, 1)


def test_pane_is_lazy_during_scan_and_remembers_fold_state(qapp, tmp_path, sample_tree) -> None:
    settings = QSettings(str(tmp_path / 'details.ini'), QSettings.Format.IniFormat)
    panel = DetailsPanel(settings)
    root = scan(sample_tree).root
    panel.set_node(root)
    assert not panel.toggle.isChecked() and not panel._timer.isActive() and not panel._running
    panel.toggle.setChecked(True)
    panel.resize(350, 270)
    panel.show()
    _wait(qapp, lambda: panel._result is not None)
    assert sum(size for size, _ in panel._result.types.values()) == root.size
    assert f'Size: {format_size(root.size)}' in panel.facts.text()
    qapp.processEvents()
    assert panel.facts.height() >= panel.facts.fontMetrics().lineSpacing() * 5
    panel.set_node(root, live=True)
    assert panel._result is None and not panel._timer.isActive()
    assert panel.distribution.text() == 'Distribution is available when scanning finishes.'
    panel.toggle.setChecked(False)
    assert settings.value('details_expanded', type=bool) is False
    panel.stop(wait=True)
    panel.close()
    panel.deleteLater()


def test_selection_details_replace_stale_results_and_join_on_close(window, qapp, sample_tree) -> None:
    window.results.show_outcome(analyse(scan(sample_tree)))
    panel = window.results.details
    panel.toggle.setChecked(True)
    _wait(qapp, lambda: panel._result is not None)
    root = window.results.outcome.result.root
    file = next(node for node in root.children if node.name == 'big.bin')
    old = SimpleNamespace()
    panel.set_node(file)
    panel._done(old, breakdown(root, panel.now))
    assert panel._result is None
    _wait(qapp, lambda: panel._result is not None)
    assert sum(size for size, _ in panel._result.types.values()) == file.size
    window.results.begin_scan()
    assert panel.node is None and panel._result is None
    window.close()
    assert not any(worker.isRunning() for worker in panel._running)
