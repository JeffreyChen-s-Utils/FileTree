"""Exact optional size bounds and local calendar bounds for the search dialog."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from je_file_tree.gui.i18n import tr
from je_file_tree.gui.optional_date import OptionalDateEdit

INPUT_LIMIT = 128
MAX_BYTES = (1 << 63) - 1
UNITS = ("B", "KiB", "MiB", "GiB", "TiB")


def editable_size(value: int, preferred: str = "auto") -> tuple[str, str]:
    """Return an exact, finite input value and binary unit without display rounding."""
    validate_sizes(value, None)
    display_units = ("B", "KB", "MB", "GB", "TB", "PB")
    if preferred == "auto":
        power = 0
        while power < len(UNITS) - 1 and value >= 1024 ** (power + 1):
            power += 1
    else:
        power = min(display_units.index(preferred), len(UNITS) - 1)
    whole, remainder = divmod(value, 1024 ** power)
    if not remainder:
        return str(whole), UNITS[power]
    digits = 10 * power
    fraction = str(remainder * 5 ** digits).zfill(digits).rstrip("0")
    return f"{whole}.{fraction}", UNITS[power]


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
        self.field_errors: dict[QWidget, QLabel] = {}
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        for field, unit, key in ((self.minimum, self.min_unit, "search_larger"),
                                 (self.maximum, self.max_unit, "search_smaller")):
            field.setMaxLength(INPUT_LIMIT)
            unit.addItems(UNITS)
            unit.setAccessibleName(tr(key) + " " + tr("search_size_unit"))
            row = QHBoxLayout()
            row.addWidget(field, 1)
            row.addWidget(unit)
            self._add_field(form, field, key, row)
        self.start = OptionalDateEdit(_date_text(state.get("date_start")))
        self.through = OptionalDateEdit(_date_text(state.get("date_through")))
        for field, key in ((self.start, "search_date_start"), (self.through, "search_date_through")):
            row = QHBoxLayout()
            row.addWidget(field)
            self._add_field(form, field, key, row)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setTextFormat(Qt.TextFormat.PlainText)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr('date_accept'))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('date_cancel'))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        hint = QLabel(tr("search_range_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addWidget(self.buttons)
        self.setMinimumWidth(460)

    def _add_field(self, form: QFormLayout, field: QWidget, key: str, row: QHBoxLayout) -> None:
        label = QLabel(tr(key))
        label.setBuddy(field)
        field.setAccessibleName(tr(key))
        if isinstance(field, OptionalDateEdit):
            field.edit.setAccessibleName(tr(key))
        error = QLabel()
        error.setTextFormat(Qt.TextFormat.PlainText)
        error.setWordWrap(True)
        error.hide()
        self.field_errors[field] = error
        block = QVBoxLayout()
        block.addLayout(row)
        block.addWidget(error)
        form.addRow(label, block)

    def _fail(self, field: QWidget, message: str) -> None:
        self.field_errors[field].setText(message)
        self.field_errors[field].show()
        field.setAccessibleDescription(message)
        self.error.setText(tr("search_fix_field"))
        field.setFocus()
        if isinstance(field, OptionalDateEdit):
            field.edit.setAccessibleDescription(message)
            field.edit.selectAll()
        elif isinstance(field, QLineEdit):
            field.selectAll()

    def _sizes(self) -> tuple[int | None, int | None] | None:
        values = []
        for field, unit in ((self.minimum, self.min_unit), (self.maximum, self.max_unit)):
            try:
                values.append(exact_bytes(field.text(), unit.currentText()))
            except ValueError as error:
                self._fail(field, str(error))
                return None
        try:
            validate_sizes(*values)
        except ValueError as error:
            self._fail(self.maximum, str(error))
            return None
        return values[0], values[1]

    def _dates(self) -> tuple[str, str] | None:
        start, through = self.start.text().strip(), self.through.text().strip()
        for field, value in ((self.start, start), (self.through, through)):
            try:
                calendar_bounds(value if field is self.start else "", value if field is self.through else "")
            except ValueError as error:
                self._fail(field, str(error))
                return None
        try:
            calendar_bounds(start, through)
        except ValueError as error:
            self._fail(self.through, str(error))
            return None
        return start, through

    def accept(self) -> None:
        """Commit a valid draft, or retain it and focus the field that needs correction."""
        for field, error in self.field_errors.items():
            error.hide()
            field.setAccessibleDescription("")
            if isinstance(field, OptionalDateEdit):
                field.edit.setAccessibleDescription("")
        self.error.clear()
        sizes = self._sizes()
        if sizes is None:
            return
        dates = self._dates()
        if dates is None:
            return
        self.values = {"min_size": sizes[0], "max_size": sizes[1],
                       "date_start": dates[0], "date_through": dates[1]}
        super().accept()


def _size_text(value: Any) -> str:
    return "" if value is None else str(value)


def _date_text(value: Any) -> str:
    return "" if value is None else str(value)
