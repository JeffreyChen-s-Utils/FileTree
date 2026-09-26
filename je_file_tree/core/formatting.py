"""Turn sizes, counts, shares and times into short display text."""

from __future__ import annotations

import time

# Binary units, which is what Windows Explorer, macOS before 10.6 and most
# disk tools show. The labels say KB/MB/GB because that is what people read.
SIZE_UNITS: tuple[str, ...] = ("B", "KB", "MB", "GB", "TB", "PB")
AUTO_UNIT = "auto"
_STEP = 1024


def format_size(size: int, unit: str = AUTO_UNIT) -> str:
    """``size`` bytes as text, e.g. ``"1.5 GB"``.

    ``unit`` is ``"auto"`` (the largest unit that keeps the number at 1 or
    more) or one of ``SIZE_UNITS``. Bytes are shown whole, other units with
    one decimal.
    """
    if unit != AUTO_UNIT and unit not in SIZE_UNITS:
        raise ValueError(f"unknown size unit: {unit!r}")
    if unit == AUTO_UNIT:
        power = 0
        value = float(abs(size))
        while value >= _STEP and power < len(SIZE_UNITS) - 1:
            value /= _STEP
            power += 1
    else:
        power = SIZE_UNITS.index(unit)
    if power == 0:
        return f"{size:,} B"
    return f"{size / _STEP ** power:,.1f} {SIZE_UNITS[power]}"


def format_count(count: int) -> str:
    """A count with thousands separators, e.g. ``"12,345"``."""
    return f"{count:,}"


def format_share(share: float) -> str:
    """A 0..1 fraction as a percentage with one decimal, e.g. ``"42.5 %"``."""
    return f"{share * 100:.1f} %"


def format_time(timestamp: float) -> str:
    """A POSIX timestamp as local ``YYYY-MM-DD HH:MM`` ("" for 0 or an unrepresentable time)."""
    if timestamp <= 0:
        return ""
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp))
    except (OverflowError, OSError, ValueError):
        return ""

