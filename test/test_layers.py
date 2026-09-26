"""``je_file_tree.core`` stays free of Qt, so it can be used and tested without a GUI."""

from __future__ import annotations

import ast
from pathlib import Path

_CORE = Path(__file__).resolve().parents[1] / "je_file_tree" / "core"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_the_core_imports_neither_qt_nor_the_gui() -> None:
    modules = sorted(_CORE.glob("*.py"))
    assert len(modules) >= 6
    bad = {path.name: sorted(name for name in _imports(path)
                             if name.split(".")[0] == "PySide6" or name.startswith("je_file_tree.gui"))
           for path in modules}
    assert {name: found for name, found in bad.items() if found} == {}
