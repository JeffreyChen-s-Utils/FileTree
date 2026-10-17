"""Validate immutable restart choices and keep imported workspace defaults in memory."""

from __future__ import annotations

from dataclasses import dataclass

from je_file_tree.core.scanner import ScanOptions

MAX_SCAN_WORKERS = 32
SCAN_FLAGS = (("hidden", "include_hidden"), ("gentle", "gentle"),
              ("capture_file_times", "file_times"), ("capture_owners", "windows_owners"),
              ("exact_allocation", "exact_windows_allocation"), ("count_hard_links", "count_hard_links"))
_FIELDS = frozenset(field for _action, field in SCAN_FLAGS)


@dataclass(slots=True)
class ScanDefaults:
    """Transient shared defaults; explicit preference edits update this and the saved setting."""

    workers: int
    exclude: tuple[str, ...]


def valid_scan_preferences(options: tuple[ScanOptions, ...], count: int) -> bool:
    """Allow only existing GUI scan choices, with shared exclusion/concurrency defaults."""
    if type(options) is not tuple or len(options) != count or not options:
        return False
    for item in options:
        if (type(item) is not ScanOptions or item.experimental_mft is not False
                or not all(type(getattr(item, field)) is bool for field in _FIELDS)
                or type(item.workers) is not int or not 1 <= item.workers <= MAX_SCAN_WORKERS
                or type(item.exclude) is not tuple
                or not all(isinstance(pattern, str) and "\0" not in pattern for pattern in item.exclude)):
            return False
    return all((item.workers, item.exclude) == (options[0].workers, options[0].exclude) for item in options)


def encode_scan_preferences(options: tuple[ScanOptions, ...]) -> dict[str, object]:
    """Encode shared defaults once and each tab's six current next-scan flags separately."""
    return {"defaults": {"workers": options[0].workers, "exclude": options[0].exclude},
            "options": [{field: getattr(item, field) for field in _FIELDS} for item in options]}


def decode_scan_preferences(defaults: object, flags: object) -> tuple[ScanOptions, ...]:
    """Decode strict data only; private scanner backends and operation authority are not accepted."""
    if (not isinstance(defaults, dict) or set(defaults) != {"workers", "exclude"}
            or not isinstance(defaults["exclude"], list) or not isinstance(flags, list)):
        raise ValueError("Invalid workspace scan defaults")
    options = []
    for item in flags:
        if not isinstance(item, dict) or set(item) != _FIELDS:
            raise ValueError("Invalid workspace scan flags")
        options.append(ScanOptions(**item, workers=defaults["workers"], exclude=tuple(defaults["exclude"])))
    result = tuple(options)
    if not valid_scan_preferences(result, len(flags)):
        raise ValueError("Invalid workspace scan preferences")
    return result
