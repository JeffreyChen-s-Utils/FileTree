"""Qt accessibility properties and keyboard navigation stay bounded and follow all charts."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest

from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanResult
from je_file_tree.gui.charts import BARS, MODES, TREE
from je_file_tree.gui.main_window import RESULTS_PAGE
from je_file_tree.gui.scan_worker import analyse


def _tree():
    root = Node('/root', True, size=1000, children=[])
    folder = Node('folder', True, size=900, allocated=900, parent=root, children=[])
    nested = Node('nested', True, size=800, allocated=800, parent=folder, children=[])
    nested.children.append(Node('large.mp4', False, size=800, parent=nested))
    folder.children.extend([nested, Node('small.jpg', False, size=100, parent=folder)])
    root.children.extend([folder, Node('text.txt', False, size=100, parent=root)])
    return root, folder, nested


@pytest.mark.parametrize('mode', MODES)
def test_keyboard_selection_open_up_and_qt_accessibility(window, qapp, mode) -> None:
    root, folder, nested = _tree()
    window.results.show_outcome(analyse(ScanResult(root, [], 0)))
    window.pages.setCurrentIndex(RESULTS_PAGE)
    window.results.set_chart_mode(mode)
    window.show()
    window.activateWindow()
    charts = window.results.charts
    chart = charts.current_chart()
    chart.setFocus()
    qapp.processEvents()
    interface = QAccessible.queryAccessibleInterface(chart)
    assert interface is not None
    assert interface.text(QAccessible.Text.Name) == chart.accessibleName() and chart.accessibleName()
    assert 'Enter opens a folder' in interface.text(QAccessible.Text.Description)
    QTest.keyClick(chart, Qt.Key.Key_Down)
    assert chart._selected is folder and window.results.selected_node() is folder
    assert 'Selected: ' + folder.path in chart.accessibleDescription()
    QTest.keyClick(chart, Qt.Key.Key_Return)
    assert all(view.view_root is folder for view in charts._charts.values())
    charts.set_selected(nested)
    QTest.keyClick(chart, Qt.Key.Key_Return)
    assert charts.view_root is nested
    assert 'Selected: ' + nested.path in chart.accessibleDescription()
    QTest.keyClick(chart, Qt.Key.Key_Backspace)
    assert charts.view_root is folder
    QTest.keyClick(chart, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
    assert charts.view_root is nested, 'Alt+Left still steps the breadcrumb visits'


@pytest.mark.parametrize('mode', MODES)
def test_enter_never_opens_a_file_link_or_detached_selection(window, qapp, mode) -> None:
    root, _folder, _nested = _tree()
    window.results.show_outcome(analyse(ScanResult(root, [], 0)))
    charts = window.results.charts
    charts.set_mode(mode)
    chart = charts.current_chart()
    for node in (root.children[-1], Node('link', True, is_link=True, parent=root), Node('/detached', True)):
        charts.set_selected(node)
        QTest.keyClick(chart, Qt.Key.Key_Return)
        assert charts.view_root is root


def test_bar_keyboard_selection_scrolls_last_bounded_row_into_view(window, qapp) -> None:
    root = Node('/root', True, size=10000, children=[])
    root.children.extend(Node(str(number), False, size=100, parent=root) for number in range(250))
    window.results.show_outcome(analyse(ScanResult(root, [], 0)))
    window.pages.setCurrentIndex(RESULTS_PAGE)
    charts = window.results.charts
    charts.set_mode(BARS)
    window.show()
    qapp.processEvents()
    nodes = charts._access[BARS]._nodes()
    assert len(nodes) == 101
    charts.set_selected(nodes[-2])
    QTest.keyClick(charts.bars, Qt.Key.Key_Down)
    assert charts.bars._selected is nodes[-1]
    assert charts._pages[BARS].verticalScrollBar().value() > 0


def test_tree_keeps_folder_expansion_and_descriptions_retranslate(window, qapp) -> None:
    root, folder, _nested = _tree()
    window.results.show_outcome(analyse(ScanResult(root, [], 0)))
    charts = window.results.charts
    charts.set_mode(TREE)
    charts.set_selected(folder)
    QTest.keyClick(charts.tree, Qt.Key.Key_Right)
    assert id(folder) in charts.tree._expanded
    QTest.keyClick(charts.tree, Qt.Key.Key_Left)
    assert id(folder) not in charts.tree._expanded
    window.change_language('zh-TW')
    assert all('Enter 開啟資料夾' in chart.accessibleDescription() for chart in charts._charts.values())
    assert charts.bars.accessibleName() == '長條圖'
