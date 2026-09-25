"""The scan's reasons for entries it could not read, in the window's language."""

from __future__ import annotations

from file_tree.core.scanner import ACCESS_DENIED, NOT_FOUND, NOT_SCANNED, PATH_TOO_LONG
from file_tree.gui.i18n import tr

_REASON_KEYS = {ACCESS_DENIED: "problem_access_denied", NOT_FOUND: "problem_not_found",
                PATH_TOO_LONG: "problem_path_too_long", NOT_SCANNED: "problem_not_scanned"}


def problem_text(reason: str) -> str:
    """A reason worded by the scanner, translated; any other (the system's own text) as it is."""
    key = _REASON_KEYS.get(reason)
    return tr(key) if key else reason
