"""Native bin proof using only the live fresh owned VHDX drive; fixture approval is scoped explicitly."""

from dataclasses import asdict
from pathlib import Path
import shutil
import time
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from je_file_tree.core.allocation import allocation_unit
from je_file_tree.core.capacity import capacity_ledger
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.core.trash_size import trash_usage, _shell32
from je_file_tree.gui import bin_dialog as bins
from je_file_tree.gui.file_actions import trash_receipt
from je_file_tree.gui.volumes import Volume, VolumesWorker
from tools.windows_owned_volume import OwnedVolume, require, verify_volume
from tools.volume_evidence import ledger_record

_TIMEOUT = 20
_BYTES = 2 * 1024 * 1024
_EMPTY_FLAGS = 7
_QUESTIONS = 2
_ARRIVAL_COUNT = 2


def _wait(app: QApplication, predicate) -> None:
    deadline = time.monotonic() + _TIMEOUT
    while not predicate():
        require(time.monotonic() < deadline, "Private native bin GUI did not complete in time")
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def _trash(volume: OwnedVolume, name: str) -> None:
    verify_volume(volume)
    path = volume.root / "owned-bin-fixtures" / name
    require(not path.exists(), "Refusing an existing bin fixture source")
    with path.open("xb") as stream:
        stream.write(b"owned bin payload\n" * (_BYTES // 18))
    receipt = trash_receipt(str(path))
    require(receipt.success and not path.exists(), "Native Trash did not move the owned fixture")
    if receipt.destination:
        require(Path(receipt.destination).is_relative_to(volume.root), "Owned Trash escaped its private volume")


def _row(volume: OwnedVolume) -> Volume:
    verify_volume(volume)
    usage = shutil.disk_usage(volume.root)
    trash = trash_usage(str(volume.root))
    require(trash is not None and trash.complete, "Native private-bin query failed")
    return Volume(str(volume.root), volume.label, "NTFS", usage.total, usage.used, usage.free,
                  allocation_unit(str(volume.root)), trash)


def _question(dialog, volume: OwnedVolume, messages: list[str], answer, arrival: bool = False):
    def question(parent, _title, message, _buttons, default):
        verify_volume(volume)
        require(parent is dialog and str(volume.root) in message and default == QMessageBox.StandardButton.No,
                "Question escaped the exact reviewed private fixture scope/default")
        messages.append(message)
        if arrival and len(messages) == 1:
            _trash(volume, "arrival 測試.bin")
        return answer
    return question


def _settled(app: QApplication, dialog) -> None:
    _wait(app, lambda: dialog._empty_worker is None and not dialog.worker.isRunning())
    require(dialog.model.rowCount() == 1, "Fixture survey lost its exact volume row")
    dialog.view.setCurrentIndex(dialog.proxy.index(0, 0))


def _review(app: QApplication, dialog, volume: OwnedVolume, answer, *, arrival: bool = False) -> list[str]:
    messages = []
    with patch.object(bins, "ask_bin", _question(dialog, volume, messages, answer, arrival)):
        dialog.empty_selected()
        if answer == QMessageBox.StandardButton.Yes:
            require(not dialog.stop_button.isEnabled() and not dialog.close_box.isEnabled()
                    and not dialog.view.isEnabled(), "Active native bin operation did not guard its lifetime")
            dialog.reject()
            require(not dialog._closed, "Close destroyed an active native bin operation")
        _settled(app, dialog)
    return messages


def bin_proof(volume: OwnedVolume) -> dict:
    """Verify default-No, arrivals, native scoped emptying, joined lifetime and metadata refresh.

    Override only the GUI volume survey to the owned drive and explicit fixture question responses.
    Actual Shell query, QFile Trash, approval recheck, worker and SHEmptyRecycleBinW remain native.
    Revalidate the UUID handle's physical mapping and volume GUID before every fixture mutation.
    No host bin is queried or emptied. Only disposable payloads created here can enter the test bin.
    """
    verify_volume(volume)
    app = QApplication.instance() or QApplication([])
    initial = _row(volume).trash
    require(initial.count == initial.size == 0, "A fresh fixture unexpectedly contains existing bin data")
    (volume.root / "owned-bin-fixtures").mkdir()
    _trash(volume, "first 測試.bin")
    before = _row(volume).trash
    require(before.count == 1 and before.size > 0, "Native private bin did not report the owned payload")
    native_empty, called = _shell32().SHEmptyRecycleBinW, []
    def empty(window, root, flags):
        verify_volume(volume)
        require(root == str(volume.root) and flags == _EMPTY_FLAGS, "Native empty attempted a foreign/global bin")
        called.append(root)
        return native_empty(window, root, flags)
    def survey(worker):
        if not worker.cancel.is_set():
            worker.ready.emit([_row(volume)], 1)
    with patch.object(VolumesWorker, "run", survey), patch.object(_shell32(), "SHEmptyRecycleBinW", empty):
        dialog = bins.BinDialog("auto")
        try:
            _settled(app, dialog)
            declined = _review(app, dialog, volume, QMessageBox.StandardButton.No)
            require(len(declined) == 1 and not called and _row(volume).trash == before,
                    "Declined approval changed the native bin")
            changed = _review(app, dialog, volume, QMessageBox.StandardButton.Yes, arrival=True)
            after_arrival = _row(volume).trash
            require(len(changed) == _QUESTIONS and not called and bool(dialog.last_error)
                    and after_arrival.count == _ARRIVAL_COUNT,
                    "Changed native totals did not refuse execution/refresh the failure")
            refusal = dialog.last_error
            ledger = capacity_ledger(scan(volume.root, options=ScanOptions(exact_windows_allocation=True)).root)
            free_before = shutil.disk_usage(volume.root).free
            approved = _review(app, dialog, volume, QMessageBox.StandardButton.Yes)
            _wait(app, lambda: _row(volume).trash.count == 0)
            after = _row(volume).trash
            require(len(approved) == _QUESTIONS and called == [str(volume.root)] and not dialog.last_error
                    and after.size == after.count == 0 and dialog.model.rows()[0].trash == after,
                    "Native scoped emptying/result refresh failed")
            require(ledger.recycle_bin_seen is not None and ledger.recycle_bin_seen > 0,
                    "Recorded bin allocation was not attributed as an included subset")
            return {"before": asdict(before), "arrival": asdict(after_arrival), "after": asdict(after),
                    "native_calls": called, "declined_preserved": True, "arrival_refused": refusal,
                    "two_questions": approved, "active_close_refused": True,
                    "ledger_before_empty": ledger_record(ledger), "free_before": free_before,
                    "free_after": shutil.disk_usage(volume.root).free}
        finally:
            dialog.shutdown()
            dialog.reject()
            dialog.deleteLater()
            app.processEvents()
