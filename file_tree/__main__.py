"""``python -m file_tree [folder]`` opens the window (and starts scanning ``folder`` if given)."""

import sys

from file_tree.gui.app import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
