"""Regenerate the README screenshots: ``py -3 tools/make_screenshots.py``.

The window shows a made-up home folder built in memory (nothing is read from
disk), so the pictures are the same on every machine and show no real paths.
Writes ``docs/images/main_window_<language>.png`` for every language.
"""

from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from je_file_tree.core.node import Node  # noqa: E402
from je_file_tree.core.scanner import ScanResult  # noqa: E402
from je_file_tree.gui.app import create_workspace  # noqa: E402
from je_file_tree.gui.i18n import LANGUAGES  # noqa: E402
from je_file_tree.gui.main_window import RESULTS_PAGE  # noqa: E402
from je_file_tree.gui.scan_worker import analyse  # noqa: E402

OUTPUT = ROOT / "docs" / "images"
MB = 1024 * 1024
_FOLDERS = {
    "Videos": [("holiday-2025.mp4", 4200), ("birthday.mov", 1900), ("screen-recording.mkv", 850)],
    "Games": [("assets.pak", 3800), ("textures.pak", 2100), ("game.exe", 180), ("engine.dll", 95)],
    "Downloads": [("installer.msi", 720), ("dataset.zip", 1450), ("manual.pdf", 25), ("setup.exe", 310)],
    "Pictures": [(f"IMG_{number:04d}.jpg", 6) for number in range(60)] + [("panorama.png", 140)],
    "Music": [(f"track-{number:02d}.flac", 32) for number in range(30)],
    "Documents": [("report.docx", 3), ("budget.xlsx", 2), ("thesis.pdf", 48), ("notes.txt", 1)],
    "Projects": [("build.log", 12), ("main.py", 1), ("data.json", 64), ("backup.7z", 900)],
}


def demo_tree() -> Node:
    """A home folder with typical content and sizes."""
    rng = random.Random(7)  # noqa: S311 - made-up sizes for a picture, not security
    root = Node("C:\\Users\\demo", True, children=[])
    for folder_name, files in _FOLDERS.items():
        folder = Node(folder_name, True, children=[], parent=root)
        root.children.append(folder)
        for name, megabytes in files:
            size = int(megabytes * MB * rng.uniform(0.8, 1.2))
            folder.children.append(Node(name, False, size=size, allocated=-(-size // 4096) * 4096, file_count=1,
                                        modified=1_780_000_000 + rng.randint(0, 9_000_000), parent=folder))
    _add_up(root)
    return root


def _add_up(root: Node) -> None:
    for folder in root.children:
        folder.size = sum(child.size for child in folder.children)
        folder.allocated = sum(child.allocated for child in folder.children)
        folder.file_count = len(folder.children)
        folder.modified = max(child.modified for child in folder.children)
        folder.children.sort(key=lambda node: -node.size)
    root.size = sum(folder.size for folder in root.children)
    root.allocated = sum(folder.allocated for folder in root.children)
    root.file_count = sum(folder.file_count for folder in root.children)
    root.dir_count = len(root.children)
    root.modified = max(folder.modified for folder in root.children)
    root.children.sort(key=lambda node: -node.size)


def main() -> None:
    """Render one screenshot per language."""
    app = QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scratch = tempfile.TemporaryDirectory()  # throw-away settings, never the user's own
    for language in LANGUAGES:
        settings = QSettings(str(Path(scratch.name) / f"{language}.ini"), QSettings.Format.IniFormat)
        settings.setValue("language", language)
        window = create_workspace(settings)
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        window.resize(1200, 720)
        window.show()
        window.current.results.show_outcome(analyse(ScanResult(demo_tree(), [], 2.4)))
        window.current.pages.setCurrentIndex(RESULTS_PAGE)
        window.current.path_edit.setText("C:\\Users\\demo")
        for _ in range(10):
            app.processEvents()
        window.grab().save(str(OUTPUT / f"main_window_{language}.png"))
        window.close()
        window.deleteLater()


if __name__ == "__main__":
    main()
