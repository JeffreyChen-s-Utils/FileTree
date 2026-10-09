"""Chart navigation retains bounded history without retaining detached branches."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMenu, QToolButton

from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanResult
from je_file_tree.gui.breadcrumbs import Breadcrumbs, FolderHistory
from je_file_tree.gui.main_window import RESULTS_PAGE
from je_file_tree.gui.results_view import CHART_TAB
from je_file_tree.gui.scan_worker import analyse


def _tree():
    root = Node('/root', True, children=[])
    children = [Node(name, True, size=1, children=[], parent=root) for name in ('a', 'b', 'c')]
    root.children.extend(children)
    return root, children


def test_history_branches_and_resets_with_a_new_scan() -> None:
    root, (a, b, c) = _tree()
    history = FolderHistory()
    history.set_root(root)
    for node in (root, a, b):
        history.visit(node)
    assert history.step(-1) is a
    assert history.step(1) is b
    assert history.step(-1) is a
    history.visit(c)
    assert history.entries == [root, a, c]
    assert history.step(1) is None
    history.set_root(root)
    assert history.current is c
    history.set_root(Node('/other', True))
    assert history.entries == [] and history.position == -1


def test_history_is_bounded_and_prunes_detached_visits() -> None:
    root, children = _tree()
    history = FolderHistory()
    history.set_root(root)
    for number in range(150):
        history.visit(children[number % 3])
    assert len(history.entries) == 100
    children[-1].detach()
    assert history.step(-1) in children[:2]
    assert all(node in children[:2] for node in history.entries)
    history.visit(Node('file', False, parent=root))
    history.visit(Node('link', True, is_link=True, parent=root))
    assert history.current in children[:2]


def test_deep_breadcrumbs_have_six_labels_and_a_complete_ancestor_menu(qapp) -> None:
    root = Node('/root', True, children=[])
    node = root
    for number in range(1100):
        child = Node(str(number), True, children=[], parent=node)
        node.children.append(child)
        node = child
    crumbs = Breadcrumbs()
    crumbs.set_root(root)
    crumbs.visit(node)
    crumbs.resize(280, 46)
    crumbs.show()
    qapp.processEvents()
    buttons = crumbs._container.findChildren(QToolButton)
    assert len(buttons) == 7
    assert buttons[-1].toolTip() == node.path and not buttons[-1].isEnabled()
    assert crumbs.width() == 280 and crumbs._scroll.horizontalScrollBar().maximum() > 0
    assert crumbs._scroll.horizontalScrollBar().value() == crumbs._scroll.horizontalScrollBar().maximum()
    selected = []
    crumbs.navigate.connect(selected.append)
    buttons[1].click()
    menu = crumbs.findChild(QMenu)
    assert len(menu.actions()) == 1095
    menu.actions()[0].trigger()
    menu.close()
    assert selected[0] is root.children[0]
    crumbs.set_root(Node('/new', True))
    assert crumbs._node is None and not crumbs.back.isEnabled()
    crumbs.close()
    crumbs.deleteLater()


def test_breadcrumbs_follow_all_charts_and_shortcuts(window, qapp) -> None:
    root, (a, b, c) = _tree()
    window.results.show_outcome(analyse(ScanResult(root, [], 0)))
    window.results.tabs.setCurrentIndex(CHART_TAB)
    window.pages.setCurrentIndex(RESULTS_PAGE)
    window.show()
    window.activateWindow()
    charts, crumbs = window.results.charts, window.results.breadcrumbs
    for node in (a, b):
        charts.set_view_root(node)
    qapp.processEvents()
    crumbs.back.click()
    assert all(chart.view_root is a for chart in charts._charts.values())
    assert crumbs.history.entries == [root, a, b]
    QTest.keyClick(window, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    qapp.processEvents()
    assert charts.view_root is b
    QTest.keyClick(window, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
    qapp.processEvents()
    assert charts.view_root is a
    charts.set_view_root(c)
    assert not crumbs.forward.isEnabled()
    window.results.begin_scan()
    assert crumbs.history.entries == []
