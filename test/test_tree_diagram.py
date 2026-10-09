"""Bounded hierarchy layout and the fourth coordinated chart mode."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan
from je_file_tree.core.tree_layout import layout
from je_file_tree.gui.charts import TREE, ChartStack
from je_file_tree.gui.tree_diagram import VERTICAL


def test_wide_tree_is_paged_and_bounded() -> None:
    root = Node("root", True, children=[])
    for size in range(1000):
        child = Node(str(size), True, allocated=size, parent=root, children=[])
        root.children.append(child)
    rows = layout(root, max_visible=12)
    assert len(rows) == 12
    assert [item.node.name for item in rows[1:-1]] == [str(n) for n in range(999, 989, -1)]
    assert rows[-1].node is None and rows[-1].hidden_count == 990
    assert rows[-1].hidden_size == sum(range(990))
    paged = layout(root, visible_counts={id(root): 20}, max_visible=25)
    assert len(paged) == 22 and paged[-1].hidden_count == 980
    later = layout(root, visible_counts={id(root): 10}, page_offsets={id(root): 240}, max_visible=12)
    assert [row.node.name for row in later[1:-1]] == [str(n) for n in range(759, 749, -1)]
    assert later[-1].hidden_count == 750


def test_deep_tree_never_recurses_or_exceeds_the_visible_limit() -> None:
    root = Node("root", True, children=[])
    node = root
    expanded = set()
    for number in range(2500):
        child = Node(str(number), True, allocated=1, parent=node, children=[])
        node.children.append(child)
        expanded.add(id(child))
        node = child
    rows = layout(root, expanded=frozenset(expanded), max_visible=100)
    assert len(rows) == 100
    assert rows[-1].depth == 99
    assert [item.parent for item in rows[1:]] == list(range(99))


def test_unavailable_branch_does_not_expose_stale_children() -> None:
    root = Node("root", True, children=[])
    blocked = Node("blocked", True, error="NOT_SCANNED", parent=root, children=[])
    stale = Node("stale", True, allocated=50, parent=blocked, children=[])
    blocked.children.append(stale)
    root.children.append(blocked)

    rows = layout(root, expanded=frozenset({id(blocked)}))
    assert [item.node for item in rows] == [root, blocked]


def test_tree_chart_expands_and_keeps_selection_in_sync(qapp: QApplication, sample_tree: Path) -> None:
    root = scan(sample_tree).root
    photos = next(child for child in root.children if child.name == "photos")
    nested = Node("archive", True, allocated=20, parent=photos, children=[])
    photos.children.append(nested)
    charts = ChartStack()
    charts.resize(700, 450)
    charts.set_view_root(root)
    charts.set_mode(TREE)
    tree = charts.tree
    assert charts.mode == TREE
    assert photos in [item.node for item in tree.rows()]
    item = next(item for item in tree.rows() if item.node is photos)
    rect = tree.card_rect(item)
    QTest.mouseClick(tree, Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
    assert tree._selected is not photos  # selection is driven by the connected results page
    charts.set_selected(photos)
    assert tree._selected is photos
    QTest.mouseClick(tree, Qt.MouseButton.LeftButton,
                     pos=QPoint(round(rect.left() + 10), round(rect.center().y())))
    # The card's leading symbol opens that branch; layout now includes its children.
    assert nested in [row.node for row in tree.rows()]
    tree.set_orientation(VERTICAL)
    assert tree.orientation == VERTICAL
    assert tree.card_rect(item).y() > 0
    tree.set_zoom(1.5)
    assert tree.sizeHint().width() > 700
    tree.show()
    qapp.processEvents()
    assert not tree.grab().isNull(), "the new mode must paint as well as lay out"
    tree.resize(900, 300)
    qapp.processEvents()
    centre = tree.card_rect(item).center()
    assert tree.item_at(centre.x(), centre.y()).node is photos
    assert not tree.grab().isNull(), "resizing must retain a paintable layout"
    charts.deleteLater()
