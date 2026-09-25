"""Start FileTree from a copy of the source: ``py -3 start_file_tree.py [folder]``.

The same as ``python -m file_tree``; it is also the file Nuitka compiles into
an executable (see ``nuitka.md``).
"""

from file_tree.gui.app import run

if __name__ == "__main__":
    run()
