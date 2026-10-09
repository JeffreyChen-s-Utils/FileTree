"""Translate display-only virtual roots without inventing a filesystem path."""

from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr


def node_name(node: Node) -> str:
    """Return the captured name, or the translated name of the pathless virtual root."""
    return node.name if node.path is not None else tr("multi_roots")


def node_path(node: Node) -> str:
    """Return a display label; callers must use Node.path for actual filesystem authority."""
    return node.path if node.path is not None else tr("multi_roots")
