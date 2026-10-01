"""Background work gives way to the window while it is busy.

In CPython one thread runs Python at a time. A worker walking the tree (the scan, the analysis, clean-up
suggestions, a search) holds the interpreter lock nearly all the time, while the window needs it for
every call Qt makes into Python: each row the folder tree paints asks the model several times. So the
window queued behind the workers and hung while they ran. Measured on a 125,000-entry scan: repainting
the folder tree took 80 ms in the middle of the scan against 31 ms idle, and 2.1 s while the clean-up
suggestions were computed after it; clicks felt ignored.

``WINDOW`` is closed by the GUI while its event loop is handling something and opened when the loop is
about to wait for more; workers call ``give_way()`` at regular steps (once per folder, say), which
waits while it is closed. The wait is capped (``PAUSE_LIMIT``) so that nothing can hang on it, and the
thread that closed the gate never waits at it, so code run by the window itself is never held up.
"""

from __future__ import annotations

import threading

PAUSE_LIMIT = 0.05  # s: the longest one give_way() waits; past it the worker takes one more step


class Gate:
    """Open: workers run freely. Closed: every thread but the one that closed it waits at ``give_way``."""

    def __init__(self) -> None:
        self._open = threading.Event()
        self._open.set()
        self._closer: int | None = None

    @property
    def is_open(self) -> bool:
        """Whether workers run freely."""
        return self._open.is_set()

    def close(self) -> None:
        """Make other threads wait at ``give_way`` (called by the window's thread when it gets busy)."""
        self._closer = threading.get_ident()
        self._open.clear()

    def open(self) -> None:
        """Let the workers run (the window is idle, or about to wait for a worker to end)."""
        self._open.set()

    def give_way(self) -> None:
        """Wait while the gate is closed, at most ``PAUSE_LIMIT``; at once when open or on the closing thread."""
        if self._open.is_set() or threading.get_ident() == self._closer:
            return
        self._open.wait(PAUSE_LIMIT)


WINDOW = Gate()  # the gate the window drives; background work in the core waits at it


def give_way() -> None:
    """A step of background work: let the window go first while it is busy (see ``WINDOW``)."""
    WINDOW.give_way()
