"""Named single-path scan choices; loading never starts a scan or grants operation approval."""

from dataclasses import dataclass, replace
import json
import os

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QComboBox, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from je_file_tree.core.scanner import ScanOptions
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_preferences import (
    SCAN_FLAGS, decode_scan_preferences, encode_scan_preferences, valid_scan_preferences,
)
from je_file_tree.gui.worker_lifecycle import WorkerDialog

PRESETS_KEY = "scan_presets_v1"
MAX_PRESETS = 32
_MAX_NAME = 80
_MAX_PAYLOAD = 262144
_FIRST_PRINTABLE = 32


@dataclass(frozen=True, slots=True)
class ScanPreset:
    """A label, one absolute source and validated public GUI scan preferences."""

    name: str
    path: str
    options: ScanOptions


def _validate(presets: tuple[ScanPreset, ...]) -> None:
    if len(presets) > MAX_PRESETS:
        raise ValueError("Too many scan presets")
    names = set()
    for preset in presets:
        if (not isinstance(preset, ScanPreset) or not isinstance(preset.name, str)
                or not preset.name.strip() or preset.name != preset.name.strip() or len(preset.name) > _MAX_NAME
                or any(ord(char) < _FIRST_PRINTABLE for char in preset.name) or preset.name.casefold() in names
                or not isinstance(preset.path, str) or not os.path.isabs(preset.path) or "\0" in preset.path
                or not valid_scan_preferences((preset.options,), 1)):
            raise ValueError("Invalid scan preset")
        names.add(preset.name.casefold())


def read_presets(settings: QSettings) -> tuple[ScanPreset, ...]:
    """Read versioned data only; malformed stored settings remain untouched and visible as an error."""
    raw = settings.value(PRESETS_KEY)
    if raw is None:
        return ()
    if not isinstance(raw, str) or len(raw) > _MAX_PAYLOAD:
        raise ValueError("Invalid scan preset data")
    document = json.loads(raw)
    if (not isinstance(document, dict) or set(document) != {"version", "presets"}
            or type(document["version"]) is not int or document["version"] != 1
            or not isinstance(document["presets"], list) or len(document["presets"]) > MAX_PRESETS):
        raise ValueError("Invalid scan preset data")
    presets = []
    for item in document["presets"]:
        if (not isinstance(item, dict) or set(item) != {"name", "path", "scan"}
                or not isinstance(item["scan"], dict) or set(item["scan"]) != {"defaults", "options"}):
            raise ValueError("Invalid scan preset data")
        options = decode_scan_preferences(item["scan"]["defaults"], item["scan"]["options"])
        if len(options) != 1:
            raise ValueError("Invalid scan preset scope")
        presets.append(ScanPreset(item["name"], item["path"], options[0]))
    result = tuple(presets)
    _validate(result)
    return result


def write_presets(settings: QSettings, presets: tuple[ScanPreset, ...]) -> None:
    """Persist only supported scan fields, excluding private backends and source-operation authority."""
    _validate(presets)
    document = {"version": 1, "presets": [
        {"name": item.name, "path": item.path, "scan": encode_scan_preferences((item.options,))}
        for item in presets]}
    payload = json.dumps(document, ensure_ascii=False)
    if len(payload) > _MAX_PAYLOAD:
        raise ValueError("Scan preset data is too large")
    settings.setValue(PRESETS_KEY, payload)


class ScanPresetsDialog(WorkerDialog):
    """Edit retained choices and explicitly load one; a scan is always a separate action."""

    def __init__(self, settings: QSettings, path: str, options: ScanOptions, parent: QWidget | None = None) -> None:
        items = list(read_presets(settings))
        super().__init__(parent)
        self.settings, self.options = settings, options
        self.items = items
        self.chosen: ScanPreset | None = None
        self.setWindowTitle(tr("action_scan_presets"))
        self.resize(660, 360)
        self.list = QComboBox()
        self.list.setPlaceholderText(tr("presets_empty"))
        self.name, self.path = QLineEdit(), QLineEdit(path)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.hint = QLabel(tr("presets_hint"))
        self.hint.setWordWrap(True)
        self._build()
        self._fill()
        self.list.currentIndexChanged.connect(self._selected)
        self._selected(self.list.currentIndex())

    def _build(self) -> None:
        form = QFormLayout()
        form.addRow(tr("presets_saved"), self.list)
        form.addRow(tr("presets_name"), self.name)
        form.addRow(tr("column_path"), self.path)
        form.addRow(self.details)
        self.add = QPushButton(tr("presets_add"))
        self.update = QPushButton(tr("presets_update"))
        self.rename = QPushButton(tr("presets_rename"))
        self.remove = QPushButton(tr("presets_remove"))
        self.load = QPushButton(tr("presets_load"))
        self.add.clicked.connect(lambda: self._edit("add"))
        self.update.clicked.connect(lambda: self._edit("update"))
        self.rename.clicked.connect(lambda: self._edit("rename"))
        self.remove.clicked.connect(lambda: self._edit("remove"))
        self.load.clicked.connect(self._load)
        actions = QHBoxLayout()
        for button in (self.add, self.update, self.rename, self.remove):
            actions.addWidget(button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.addButton(self.load, QDialogButtonBox.ButtonRole.AcceptRole)
        layout = QVBoxLayout(self)
        layout.addWidget(self.hint)
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addWidget(buttons)

    def _fill(self, selected: int = -1) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for preset in self.items:
            self.list.addItem(preset.name)
        self.list.setCurrentIndex(selected)
        self.list.blockSignals(False)
        self.add.setEnabled(len(self.items) < MAX_PRESETS)

    def _selected(self, index: int) -> None:
        selected = 0 <= index < len(self.items)
        for button in (self.update, self.rename, self.remove, self.load):
            button.setEnabled(selected)
        options = self.items[index].options if selected else self.options
        if selected:
            self.name.setText(self.items[index].name)
            self.path.setText(self.items[index].path)
        flags = "; ".join(tr(f"action_{action}") for action, field in SCAN_FLAGS if getattr(options, field))
        self.details.setText(tr("presets_options", workers=options.workers, exclusions=len(options.exclude),
                                flags=flags or tr("presets_no_flags")))

    def _edit(self, action: str) -> None:
        index = self.list.currentIndex()
        if action != "add" and not 0 <= index < len(self.items):
            return
        updated = self.items.copy()
        name = self.name.text().strip()
        path = os.path.expanduser(self.path.text().strip().strip('"'))
        if action == "remove":
            updated.pop(index)
        elif action == "rename":
            updated[index] = replace(updated[index], name=name)
        elif action == "update":
            updated[index] = ScanPreset(name, path, self.options)
        else:
            updated.append(ScanPreset(name, path, self.options))
            index = len(updated) - 1
        try:
            write_presets(self.settings, tuple(updated))
        except ValueError:
            QMessageBox.warning(self, tr("action_scan_presets"), tr("presets_invalid"))
            return
        self.items = updated
        index = min(index, len(updated) - 1)
        self._fill(index)
        self._selected(index)

    def _load(self) -> None:
        index = self.list.currentIndex()
        if 0 <= index < len(self.items):
            self.chosen = self.items[index]
            self.accept()

    def shutdown(self, *, wait: bool = True) -> None:
        """Close a metadata-only editor; there are no native workers or source operations to join."""
        self.reject()
