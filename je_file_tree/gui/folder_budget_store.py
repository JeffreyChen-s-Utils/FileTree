"""One workspace owner for versioned folder budget settings and alert episodes."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QSettings, QStandardPaths, Signal

from je_file_tree.core.folder_budgets import (
    MAX_RULES, BudgetBatch, BudgetObservation, BudgetRule, BudgetTicket, budget_path,
)
from je_file_tree.gui.i18n import tr

KEY = "folder_budgets_v1"
MAX_DOCUMENT = 256_000
MAX_NAME = 160
MAX_PATH = 4096
IDENTITY_LENGTH = 32

_ERROR_KEYS = {
    "Folder budget path must be absolute": "budget_invalid_input",
    "Budget path must be absolute": "budget_invalid_input",
    "Budget path must be a native absolute directory": "budget_invalid_input",
    "Invalid folder budget rule": "budget_invalid_input",
    "Folder budget name or path is too long": "budget_invalid_input",
    "A folder budget already uses this path": "budget_duplicate_path",
    "Folder budget no longer exists": "budget_missing_rule",
    "Too many folder budgets": "budget_too_many",
    "Folder budget settings are locked": "budget_settings_locked",
    "Folder budget data location is unavailable": "budget_storage_unavailable",
    "Could not read folder budget settings": "budget_read_failed",
    "Could not save folder budget settings": "budget_write_failed",
}


def display_error(reason: str) -> str:
    """Translate known budget failures and retain OS diagnostics verbatim."""
    key = _ERROR_KEYS.get(reason)
    if key is not None:
        return tr(key)
    if reason.startswith(("Invalid folder budget", "Duplicate folder budget", "Folder budget settings exceed")):
        return tr("budget_invalid_data")
    return reason


@dataclass(frozen=True, slots=True)
class BudgetRow:
    """A rule with its last successful observation and persisted alert episode."""

    rule: BudgetRule
    observation: BudgetObservation | None = None
    alerted: bool = False
    applied: int = 0

    @property
    def status(self) -> str:
        """Return waiting, unknown, over, or within for the current rule version."""
        observation = self.observation
        if observation is None or observation.version != self.rule.version:
            return "waiting"
        if observation.bytes is None:
            return "unknown"
        return "over" if observation.bytes > self.rule.limit else "within"


class FolderBudgetStore(QObject):
    """Serialize every edit and scan publication under one settings lock."""

    changed = Signal()

    def __init__(self, settings: QSettings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.rows: tuple[BudgetRow, ...] = ()
        self.sequence = 0
        self.error = ""
        try:
            self.reload()
        except (OSError, ValueError) as error:
            self.error = str(error)

    def _lock(self) -> QLockFile:
        if self.settings.format() == QSettings.Format.IniFormat:
            target = Path(self.settings.fileName()).with_suffix(".folder-budgets.lock")
        else:
            location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
            if not location:
                raise OSError("Folder budget data location is unavailable")
            target = Path(location) / "folder-budgets.lock"
        target.parent.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(target))
        lock.setStaleLockTime(5 * 60 * 1000)
        if not lock.tryLock(0):
            raise OSError("Folder budget settings are locked")
        return lock

    def reload(self, *, notify: bool = True) -> None:
        """Read the bounded persisted document; malformed data fails visibly."""
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError("Could not read folder budget settings")
        raw = str(self.settings.value(KEY, ""))
        if len(raw) > MAX_DOCUMENT:
            raise ValueError("Folder budget settings exceed the size limit")
        try:
            data = json.loads(raw, object_pairs_hook=_unique_fields) if raw else {"sequence": 0, "rows": []}
        except (ValueError, RecursionError) as error:
            raise ValueError("Invalid folder budget settings") from error
        if (not isinstance(data, dict) or set(data) != {"sequence", "rows"}
                or type(data["sequence"]) is not int or data["sequence"] < 0):
            raise ValueError("Invalid folder budget settings")
        values = data.get("rows")
        if not isinstance(values, list) or len(values) > MAX_RULES:
            raise ValueError("Invalid folder budget rules")
        rows = tuple(_read_row(item, data["sequence"]) for item in values)
        if (len({row.rule.identity for row in rows}) != len(rows)
                or len({budget_path(row.rule.path) for row in rows}) != len(rows)):
            raise ValueError("Duplicate folder budget rules")
        self.sequence, self.rows = data["sequence"], rows
        self.error = ""
        if notify:
            self.changed.emit()

    def _save(self, rows: tuple[BudgetRow, ...], sequence: int) -> None:
        data = {"sequence": sequence, "rows": [_write_row(row) for row in rows]}
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        if len(raw) > MAX_DOCUMENT:
            raise ValueError("Folder budget settings exceed the size limit")
        previous = self.settings.value(KEY, None)
        self.settings.setValue(KEY, raw)
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            if previous is None:
                self.settings.remove(KEY)
            else:
                self.settings.setValue(KEY, previous)
            self.settings.sync()
            raise OSError("Could not save folder budget settings")
        self.sequence, self.rows, self.error = sequence, rows, ""

    def _transaction(self, transform):
        try:
            lock = self._lock()
            try:
                self.reload(notify=False)
                result = transform()
            finally:
                lock.unlock()
        except (OSError, ValueError) as error:
            self.error = str(error)
            self.changed.emit()
            raise
        self.changed.emit()
        return result

    def ticket(self) -> BudgetTicket:
        """Claim a process-wide ordered scan sequence before worker dispatch."""
        def claim() -> BudgetTicket:
            if not self.rows:
                return BudgetTicket(self.sequence, ())
            number = self.sequence + 1
            self._save(self.rows, number)
            return BudgetTicket(number, tuple(row.rule for row in self.rows))
        return self._transaction(claim)

    def put(self, name: str, path: str, limit: int, identity: str | None = None) -> BudgetRule:
        """Create or edit a rule; a path change starts a new measurement identity."""
        if len(name) > MAX_NAME or len(path) > MAX_PATH:
            raise ValueError("Folder budget name or path is too long")
        normalized = budget_path(path)

        def edit() -> BudgetRule:
            old = next((row for row in self.rows if row.rule.identity == identity), None)
            if identity is not None and old is None:
                raise ValueError("Folder budget no longer exists")
            if any(budget_path(row.rule.path) == normalized and row is not old for row in self.rows):
                raise ValueError("A folder budget already uses this path")
            if old is None and len(self.rows) >= MAX_RULES:
                raise ValueError("Too many folder budgets")
            same_path = old is not None and budget_path(old.rule.path) == normalized
            changed_limit = old is not None and old.rule.limit != limit
            rule = BudgetRule(old.rule.identity if same_path else uuid.uuid4().hex,
                              old.rule.version + int(changed_limit) if same_path else 1,
                              name.strip(), path, limit)
            row = BudgetRow(rule, old.observation if same_path else None,
                            old.alerted if same_path else False, old.applied if same_path else 0)
            rows = tuple(row if item is old else item for item in self.rows) if old else (*self.rows, row)
            self._save(rows, self.sequence)
            return rule
        return self._transaction(edit)

    def delete(self, identity: str) -> None:
        """Remove a rule without changing scanned sources."""
        def remove() -> None:
            rows = tuple(row for row in self.rows if row.rule.identity != identity)
            if len(rows) == len(self.rows):
                raise ValueError("Folder budget no longer exists")
            self._save(rows, self.sequence)
        self._transaction(remove)

    def publish(self, batch: BudgetBatch) -> tuple[BudgetRow, ...]:
        """Persist observations and alert latches before returning newly over-limit rows."""
        def apply() -> tuple[BudgetRow, ...]:
            incoming = {item.identity: item for item in batch.observations}
            rows = []
            alerts = []
            for row in self.rows:
                observation = incoming.get(row.rule.identity)
                if (observation is None or observation.version != row.rule.version
                        or observation.sequence <= row.applied or observation.sequence > self.sequence):
                    rows.append(row)
                    continue
                alerted = row.alerted
                if observation.bytes is not None:
                    if observation.bytes <= row.rule.limit:
                        alerted = False
                    elif not alerted:
                        alerted = True
                        alerts.append(row.rule.identity)
                rows.append(BudgetRow(row.rule, observation, alerted, observation.sequence))
            if tuple(rows) != self.rows:
                self._save(tuple(rows), self.sequence)
            return tuple(row for row in rows if row.rule.identity in alerts)
        return self._transaction(apply)


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate folder budget fields")
    return result


def _read_row(value: object, sequence: int) -> BudgetRow:
    if (not isinstance(value, dict)
            or set(value) != {"id", "version", "name", "path", "limit", "observation", "applied", "alerted"}):
        raise ValueError("Invalid folder budget row")
    rule = BudgetRule(value["id"], value["version"], value["name"], value["path"], value["limit"])
    if (not isinstance(rule.identity, str) or len(rule.identity) != IDENTITY_LENGTH
            or any(char not in "0123456789abcdef" for char in rule.identity)
            or len(rule.name) > MAX_NAME or len(rule.path) > MAX_PATH):
        raise ValueError("Invalid folder budget rule")
    observation = value["observation"]
    if observation is not None:
        if (not isinstance(observation, dict)
                or set(observation) != {"version", "sequence", "at", "bytes", "reason"}):
            raise ValueError("Invalid folder budget observation")
        observation = BudgetObservation(rule.identity, observation["version"], observation["sequence"],
                                        observation["at"], observation["bytes"], observation["reason"])
        if (type(observation.version) is not int or not 1 <= observation.version <= rule.version
                or type(observation.sequence) is not int or observation.sequence < 1
                or type(observation.measured_at) not in (int, float)
                or (observation.bytes is not None and
                    (type(observation.bytes) is not int or observation.bytes < 0))
                or (observation.bytes is None and
                    (not isinstance(observation.reason, str) or observation.reason not in
                     {"missing", "linked", "not_folder", "incomplete"}))
                or (observation.bytes is not None and observation.reason is not None)):
            raise ValueError("Invalid folder budget observation")
        try:
            if not math.isfinite(observation.measured_at):
                raise ValueError("Nonfinite observation time")
            datetime.fromtimestamp(observation.measured_at)
        except (OverflowError, OSError, ValueError) as error:
            raise ValueError("Invalid folder budget observation date") from error
    applied, alerted = value["applied"], value["alerted"]
    if (type(applied) is not int or not 0 <= applied <= sequence or type(alerted) is not bool
            or (observation is None and applied != 0)
            or (observation is not None and observation.sequence != applied)):
        raise ValueError("Invalid folder budget status")
    return BudgetRow(rule, observation, alerted, applied)


def _write_row(row: BudgetRow) -> dict[str, object]:
    rule, observation = row.rule, row.observation
    measured = None if observation is None else {
        "version": observation.version, "sequence": observation.sequence,
        "at": observation.measured_at, "bytes": observation.bytes, "reason": observation.reason,
    }
    return {"id": rule.identity, "version": rule.version, "name": rule.name, "path": rule.path,
            "limit": rule.limit, "observation": measured, "alerted": row.alerted, "applied": row.applied}
