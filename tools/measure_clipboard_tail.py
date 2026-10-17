"""Measure real Qt copy publication and a native consumer only in a new private Windows station."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from tools.observed_process import run_observed
from tools.windows_private_clipboard import PrivateStation, before_qt, disposable_runner, require

_RESULT = "FILETREE_CLIPBOARD_RESULT "
_MAX_ROWS = 100_000
_MAX_WIDTH = 512
_GUI_WAIT_MS = 45000


def _validate(rows: int, width: int) -> None:
    require(type(rows) is int and 1 <= rows <= _MAX_ROWS and type(width) is int and 0 <= width <= _MAX_WIDTH,
            "Require 1..100000 rows and 0..512 folder characters")


def _consumer(scope: PrivateStation) -> subprocess.Popen:
    scope.check()
    startup = subprocess.STARTUPINFO()
    startup.lpAttributeList = {"handle_list": [scope.station, scope.desktop]}
    executable = getattr(sys, "_base_executable", None) or sys.executable
    return subprocess.Popen(  # noqa: S603 - fixed reader, exact freshly created private desktop, no shell
        [executable, "-m", "tools.windows_private_clipboard", scope.station_name, scope.desktop_name,
         str(os.getpid()), str(scope.station), str(scope.desktop)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startup,
        creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)


def _instrument(app, scope: PrivateStation, state: dict) -> object:
    from PySide6.QtCore import QObject, QTimer, Signal  # noqa: PLC0415 - import only after scope verification
    from PySide6.QtWidgets import QApplication  # noqa: PLC0415

    scope.check()
    board = QApplication.clipboard()

    class Publication(QObject):
        dataChanged = Signal()  # noqa: N815 - QClipboard-compatible proxy over the real private clipboard

        def setMimeData(self, mime):  # noqa: N802
            scope.check()
            print("FILETREE_CLIPBOARD_PHASE publish-start", flush=True)
            started = time.perf_counter()
            board.setMimeData(mime)  # the clipboard takes ownership; its bytes are read only in _verify
            state.update(publish_ms=(time.perf_counter()-started)*1000, published=mime)
            print("FILETREE_CLIPBOARD_PHASE publish-complete", flush=True)
            QTimer.singleShot(0, state["start_consumer"])

    proxy = Publication(app)
    board.dataChanged.connect(proxy.dataChanged.emit)
    state["board"] = board
    return proxy


def _capture_class(state: dict):
    from je_file_tree.gui.clipboard_copy import _ClipboardCapture  # noqa: PLC0415

    class TimedCapture(_ClipboardCapture):
        def __init__(self, view):
            super().__init__(view)
            self.ready.connect(lambda header, rows: state.update(header=header, rows=rows))

        def _chunk(self):
            started = time.perf_counter()
            super()._chunk()
            state["callbacks_ms"].append((time.perf_counter()-started)*1000)

        def encoded_utf8(self):
            started = time.perf_counter()
            data = super().encoded_utf8()
            state["extract_ms"] = (time.perf_counter()-started)*1000
            return data

    return TimedCapture


def _view(rows: int, width: int):
    from je_file_tree.core.node import Node  # noqa: PLC0415
    from je_file_tree.gui import grouped_list  # noqa: PLC0415
    from je_file_tree.gui.list_transfer import install_copy  # noqa: PLC0415

    root = Node("owned-資料夾-" + "x" * width, True, children=[])
    nodes = tuple(Node(f'=entry-{row:07} "quoted"\tline\n😀', False, size=1536, parent=root) for row in range(rows))
    root.children.extend(nodes)
    model = grouped_list.GroupedListModel()
    model.set_groups([("owned", nodes)], "auto")
    view = grouped_list.build_view(model)
    view.expand(model.index(0, 0))
    grouped_list.select_entries(model, view, skip_first=False)
    install_copy(view)
    return view, model, root, nodes


def _read_result(process: subprocess.Popen, state: dict, scope: PrivateStation) -> None:
    stdout, stderr = process.communicate(timeout=5)
    state["consumer"] = {"returncode": process.returncode, "stdout": stdout.decode("utf-8", errors="replace"),
                         "stderr": stderr.decode("utf-8", errors="replace")}
    require(process.returncode == 0, "Native private clipboard consumer failed")
    state["native"] = json.loads(stdout)
    actual = state["native"]["scope"]
    require(actual["station"] == scope.station_name and actual["desktop"] == scope.desktop_name
            and actual["pid"] == process.pid and actual["noninteractive"] is True
            and state["native"]["parent_pid"] == os.getpid(), "Native consumer scope/identity differs")


def _verify(state: dict, model, root, nodes) -> None:
    from je_file_tree.core.export import spreadsheet_text  # noqa: PLC0415
    from je_file_tree.gui.clipboard_copy import UTF8_TEXT  # noqa: PLC0415

    # Read the published bytes only now, after the timed loop, so decoding never shows as a GUI pause.
    published = state.get("published")
    require(published is not None and published.formats() == [UTF8_TEXT], "Copy was not published as UTF-8 text")
    state["text"] = bytes(published.data(UTF8_TEXT)).decode("utf-8")
    state["characters"] = len(state["text"])
    expected = (state["header"], *state["rows"])
    reader = csv.reader(io.StringIO(state["text"]), delimiter="\t")
    count = 0
    for actual, row in zip(reader, expected, strict=True):
        require(actual == [spreadsheet_text(cell) for cell in row], "Copied TSV row differs")
        count += 1
    require(count == len(nodes)+1 and len(state["rows"]) == len(nodes), "Copied rows were truncated")
    require(model._groups[0].nodes is nodes and tuple(root.children) == nodes, "Owned source membership changed")
    require(model.rowCount(model.index(0, 0)) == len(nodes), "Source rows disappeared")
    normalized = state["text"].replace("\r\n", "\n")
    state["text_sha256"] = hashlib.sha256(state["text"].encode("utf-8")).hexdigest()
    require(state["native"]["normalized_sha256"] == hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            "Native CF_UNICODETEXT differs after Windows newline normalization")


def _clear(app, scope, state, view, proxy, readers) -> None:
    for process in readers:
        if process.poll() is None:
            process.kill()
            stdout, stderr = process.communicate(timeout=5)
            state["consumer"] = {"returncode": process.returncode, "stopped": "probe-deadline",
                                 "stdout": stdout.decode("utf-8", errors="replace"),
                                 "stderr": stderr.decode("utf-8", errors="replace")}
    if owner := getattr(app, "_filetree_clipboard_copy", None):
        owner.cancel()
        owner.deleteLater()
        delattr(app, "_filetree_clipboard_copy")
    scope.check()
    state["board"].clear()
    view.close()
    view.deleteLater()
    proxy.deleteLater()
    app.processEvents()


def _public_state(state: dict) -> dict:
    return {key: value for key, value in state.items() if key not in
            {"board", "text", "rows", "header", "start_consumer", "published"}}


def _timers(loop, pulse):
    from PySide6.QtCore import QTimer  # noqa: PLC0415

    timer, watchdog = QTimer(), QTimer()
    timer.timeout.connect(pulse)
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(loop.quit)
    return timer, watchdog


def _consumer_starter(scope: PrivateStation, state: dict, reader: list, loop, closing: list):
    """The reader start that setText queues; once the probe is closing it is recorded, never launched.

    After the watchdog ends the loop, cleanup still processes events, so a start queued by a late
    setText would otherwise launch a reader that nothing stops or reports.
    """
    def start_consumer():
        if closing:
            state["late_consumer_start"] = "skipped: queued start ran after the probe began closing"
            return
        try:
            reader.append(_consumer(scope))
            print("FILETREE_CLIPBOARD_PHASE native-reader-started", flush=True)
        except (OSError, RuntimeError) as error:
            state["consumer_start_error"] = {"type": type(error).__name__, "message": str(error)}
            loop.quit()

    return start_consumer


def _run_qt(app, scope: PrivateStation, rows: int, width: int, report: dict) -> dict:
    from PySide6.QtCore import QEventLoop, QTimer  # noqa: PLC0415
    from PySide6.QtGui import QShortcut  # noqa: PLC0415
    from PySide6.QtWidgets import QApplication  # noqa: PLC0415
    from je_file_tree.gui import clipboard_copy  # noqa: PLC0415

    state = {"callbacks_ms": [], "heartbeat_ms": []}
    loop, reader = QEventLoop(), []
    original_getter, original_capture = QApplication.clipboard, clipboard_copy._ClipboardCapture
    require(getattr(app, "_filetree_clipboard_copy", None) is None, "A fresh clipboard controller is required")
    view, model, root, nodes = _view(rows, width)
    started, last = time.perf_counter(), [time.perf_counter()]

    closing: list[bool] = []
    def pulse():
        now = time.perf_counter()
        state["heartbeat_ms"].append((now-last[0])*1000)
        last[0] = now
        if reader and reader[0].poll() is not None:
            loop.quit()

    state["start_consumer"] = _consumer_starter(scope, state, reader, loop, closing)
    proxy = _instrument(app, scope, state)
    QApplication.clipboard = staticmethod(lambda: proxy)
    clipboard_copy._ClipboardCapture = _capture_class(state)
    timer, watchdog = _timers(loop, pulse)
    try:
        timer.start(5)
        watchdog.start(_GUI_WAIT_MS)
        QTimer.singleShot(0, view.findChild(QShortcut).activated.emit)
        loop.exec()
        state["total_ms"] = (time.perf_counter()-started)*1000
        require(reader and reader[0].poll() is not None, "Private clipboard probe did not finish")
        _read_result(reader[0], state, scope)
        scope.check()
        _verify(state, model, root, nodes)
        require(len(view.selectionModel().selectedRows()) == rows, "Source selection changed")
        return _public_state(state)
    finally:
        closing.append(True)  # a start that setText queued must not launch a reader during cleanup
        timer.stop()
        watchdog.stop()
        QApplication.clipboard, clipboard_copy._ClipboardCapture = original_getter, original_capture
        try:
            _clear(app, scope, state, view, proxy, reader)
        finally:
            report.update(_public_state(state))


def _dispose_app(scope, app, delete, result: dict) -> None:
    try:
        scope.check()
    except (OSError, RuntimeError) as error:
        result.update(verified=False, failure={"type": type(error).__name__, "message": str(error)},
                      shutdown="Scope guard failed; skip Qt finalization and station switching")
        print(_RESULT + json.dumps(result), flush=True)
        os._exit(1)  # Owned helper only: no Qt clipboard destructor may run in an uncertain station.
    delete(app)


def _probe(rows: int, width: int) -> dict:
    _validate(rows, width)
    disposable_runner()
    before_qt()
    scope, app = PrivateStation(), None
    paths = ["je_file_tree/gui/clipboard_copy.py", "je_file_tree/gui/list_transfer.py",
             "je_file_tree/gui/grouped_list.py", "tools/measure_clipboard_tail.py",
             "tools/windows_private_clipboard.py"]
    root = Path(__file__).resolve().parents[1]
    sources = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}
    result = {"rows": rows, "folder_width": width, "pid": os.getpid(), "python": sys.version,
              "sources_sha256": sources, "commit": os.environ.get("GITHUB_SHA"), "verified": False, "measurement": {}}
    try:
        with scope:
            print("FILETREE_CLIPBOARD_SCOPE " + json.dumps(scope.check()), flush=True)
            from PySide6 import __version__ as binding_version  # noqa: PLC0415
            from PySide6.QtCore import qVersion  # noqa: PLC0415
            from PySide6.QtWidgets import QApplication  # noqa: PLC0415
            import shiboken6  # noqa: PLC0415
            try:
                app = QApplication([])
                scope.check()
                require(app.platformName() == "windows", "The native Windows Qt backend is required")
                result.update(pyside6=binding_version, qt=qVersion(), platform=app.platformName(),
                              measurement=_run_qt(app, scope, rows, width, result["measurement"]), verified=True)
            finally:
                if app is not None:
                    _dispose_app(scope, app, shiboken6.delete, result)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        result["verified"] = False
        result["failure"] = {"type": type(error).__name__, "message": str(error)[:2048]}
    result["cleanup"] = scope.cleanup
    print(_RESULT + json.dumps(result, ensure_ascii=True), flush=True)
    return result


def _result_proof(result, outcome: str) -> dict:
    stdout = (result.stdout or b"").decode("utf-8", errors="replace")
    stderr = (result.stderr or b"").decode("utf-8", errors="replace")
    records = [line.removeprefix(_RESULT) for line in stdout.splitlines() if line.startswith(_RESULT)]
    proof = {"outcome": outcome, "timeout": 60, "returncode": getattr(result, "returncode", None),
             "stdout": stdout, "stderr": stderr,
             "process_observation": getattr(result, "process_observation", {"status": "start-failed"}), "probe": None}
    if len(records) == 1:
        try:
            proof["probe"] = json.loads(records[0])
        except (ValueError, RecursionError) as error:
            proof["parse_error"] = {"type": type(error).__name__, "message": str(error)[:512]}
    return proof


def main() -> int:
    """Run one bounded fresh helper; retain raw diagnostics even when native proof fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=_MAX_ROWS)
    parser.add_argument("--width", type=int, default=80)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--_probe", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    _validate(args.rows, args.width)
    disposable_runner()
    if args._probe:
        return 0 if _probe(args.rows, args.width)["verified"] else 1
    require(args.output is not None and not args.output.exists(), "A new evidence path is required")
    command = [getattr(sys, "_base_executable", None) or sys.executable, "-m", __spec__.name,
               "--_probe", "--rows", str(args.rows), "--width", str(args.width)]
    with args.output.open("x", encoding="utf-8") as output:
        try:
            result = run_observed(command, timeout=60)
            outcome = "completed"
        except subprocess.TimeoutExpired as error:
            result, outcome = error, "timeout"
        except OSError as error:
            proof = {"outcome": "start-failed", "failure": {"type": type(error).__name__, "message": str(error)}}
            json.dump(proof, output, indent=2)
            return 1
        proof = _result_proof(result, outcome)
        json.dump(proof, output, ensure_ascii=True, indent=2)
        output.write("\n")
    return 0 if (outcome == "completed" and result.returncode == 0
                 and isinstance(proof["probe"], dict) and proof["probe"].get("verified") is True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
