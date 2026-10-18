"""Flat treemap tiles: theme-following folders, gaps and no stray outlines (U-20261018-87)."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import pytest

from je_file_tree.core.node import Node
from je_file_tree.gui.colours import contrast, readable_ink
from je_file_tree.gui.themes import theme_palette
from je_file_tree.gui.treemap_widget import CATEGORY_COLOURS, TreemapWidget, folder_colour


@pytest.mark.parametrize(("theme", "dark"), [("light", False), ("dark", True)])
def test_folder_fills_follow_the_theme_and_keep_labels_readable(theme, dark):
    palette = theme_palette(theme)
    shades = [folder_colour(depth, palette) for depth in range(3)]
    assert len({shade.name() for shade in shades}) == 3  # each depth its own shade
    assert all((shade.lightnessF() < .5) == dark for shade in shades)
    assert all(contrast(readable_ink(shade), shade) >= 4.5 for shade in shades)


def _tree() -> Node:
    root = Node("C:\\owned", True, children=[])
    folder = Node("folder", True, children=[], parent=root)
    root.children.append(folder)
    folder.children.extend(Node(f"file-{n}.zip", False, size=1000 * (n + 1), parent=folder) for n in range(4))
    folder.size = root.size = sum(child.size for child in folder.children)
    return root


def test_tiles_are_flat_with_their_own_fill_at_every_edge(qapp):
    widget = TreemapWidget()
    widget.setPalette(theme_palette("dark"))
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    widget.resize(600, 400)
    widget.show()
    widget.set_view_root(_tree())
    image = widget.grab().toImage()
    archive = QColor(CATEGORY_COLOURS["archives"])
    files = [tile for tile in widget._tiles if not tile.node.is_dir and not tile.grouped]
    assert len(files) == 4
    for tile in files:
        rect = tile.rect
        inside = [(int(rect.x + 2), int(rect.y + rect.height / 2)),            # left edge, past the gap
                  (int(rect.x + rect.width / 2), int(rect.y + rect.height - 2)),  # bottom edge
                  (int(rect.x + rect.width - 6), int(rect.y + rect.height - 6))]  # away from any label
        for x, y in inside:
            assert image.pixelColor(x, y).name() == archive.name(), (tile.node.name, x, y)
    header = next(tile for tile in widget._tiles if tile.node.name == "folder")
    strip = image.pixelColor(int(header.rect.x + header.rect.width - 4), int(header.rect.y + 3))
    assert strip.name() == folder_colour(header.depth, widget.palette()).name()
    assert strip.lightnessF() < .5  # a dark-theme folder header, not the old fixed light grey
