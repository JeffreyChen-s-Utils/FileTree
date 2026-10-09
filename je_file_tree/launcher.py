"""Absolute-path entry point for Explorer, including a source checkout outside its working directory."""

from __future__ import annotations

import os
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from je_file_tree.gui.app import run

    run()
