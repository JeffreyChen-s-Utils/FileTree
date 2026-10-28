"""Exact optional size bounds and local calendar bounds for the search dialog."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from je_file_tree.gui.i18n import tr

INPUT_LIMIT = 128
MAX_BYTES = (1 << 63) - 1
UNITS = ("B", "KiB", "MiB", "GiB", "TiB")


def exact_bytes(text: str, unit: str) -> int | None:
    """Parse a nonnegative exact byte count, rejecting fractions and overflow."""
    if not text.strip():
        return None
    try:
        if len(text) > INPUT_LIMIT:
            raise ValueError
        value = Decimal(text.strip())
        if not value.is_finite() or value < 0 or value > MAX_BYTES:
            raise ValueError
        if abs(value.as_tuple().exponent) > INPUT_LIMIT:
            raise ValueError
        numerator, denominator = value.as_integer_ratio()
        numerator *= 1024 ** UNITS.index(unit)
        result, remainder = divmod(numerator, denominator)
        if remainder or result > MAX_BYTES:
            raise ValueError
        return result
    except (InvalidOperation, ValueError, OverflowError) as error:
        raise ValueError(tr("search_range_size_error")) from error


def validate_sizes(minimum: Any, maximum: Any) -> None:
    """Check saved sizes without coercing malformed persisted values."""
    for value in (minimum, maximum):
        if value is not None and (type(value) is not int or not 0 <= value <= MAX_BYTES):
            raise ValueError(tr("search_range_size_error"))
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError(tr("search_range_order_error"))


def calendar_bounds(start: Any, through: Any) -> tuple[float | None, float | None]:
    """Convert independent inclusive local dates to a half-open timestamp interval."""
    try:
        first = _date(start)
        last = _date(through)
        if first is not None and last is not None and first > last:
            raise ValueError
        since = datetime.combine(first, time()).timestamp() if first is not None else None
        before = datetime.combine(last + timedelta(days=1), time()).timestamp() if last is not None else None
        return since, before
    except (ValueError, TypeError, OverflowError, OSError) as error:
        raise ValueError(tr("search_range_date_error")) from error


def _date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError
    return parsed


class SearchRangeDialog(QDialog):
    """Edit a draft; only a successful accept exposes applied range values."""

    def __init__(self, state: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("search_custom_ranges"))
        self.values: dict[str, Any] | None = None
        self.minimum = QLineEdit(_size_text(state.get("min_size")))
        self.maximum = QLineEdit(_size_text(state.get("max_size")))
        self.min_unit, self.max_unit = QComboBox(), QComboBox()
        form = QFormLayout()
        for field, unit, key in ((self.minimum, self.min_unit, "search_larger"),
                                 (self.maximum, self.max_unit, "search_smaller")):
            field.setMaxLength(INPUT_LIMIT)
            unit.addItems(UNITS)
            row = QHBoxLayout()
            row.addWidget(field)
            row.addWidget(unit)
            form.addRow(tr(key), row)
        self.start = QLineEdit(str(state.get("date_start") or ""))
        self.through = QLineEdit(str(state.get("date_through") or ""))
        for field, key in ((self.start, "search_date_start"), (self.through, "search_date_through")):
            field.setMaxLength(INPUT_LIMIT)
            field.setPlaceholderText(tr("search_date_format"))
            form.addRow(tr(key), field)
        self.error = QLabel()
        self.error.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        hint = QLabel(tr("search_range_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addWidget(buttons)
        self.setMinimumWidth(460)

    def accept(self) -> None:
        """Commit a valid draft, or leave the dialog open with the validation error."""
        try:
            minimum = exact_bytes(self.minimum.text(), self.min_unit.currentText())
            maximum = exact_bytes(self.maximum.text(), self.max_unit.currentText())
            validate_sizes(minimum, maximum)
            start, through = self.start.text().strip(), self.through.text().strip()
            calendar_bounds(start, through)
        except ValueError as error:
            self.error.setText(str(error))
            return
        self.values = {"min_size": minimum, "max_size": maximum,
                       "date_start": start, "date_through": through}
        super().accept()


def _size_text(value: Any) -> str:
    return "" if value is None else str(value)
