"""Headless console exports, comparison, coverage and documented exit codes."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from je_file_tree import cli
from je_file_tree.core import export
from je_file_tree.core.scanner import scan


def test_console_exports_unicode_paths_without_importing_qt(tmp_path: Path) -> None:
    folder = tmp_path / "資料夾"
    folder.mkdir()
    (folder / "檔案.txt").write_bytes(b"data")
    target = tmp_path / "tree.json"
    source = "from je_file_tree.cli import main; import sys; code=main(sys.argv[1:]); "
    source += "assert not any(m.startswith(('PySide6', 'je_file_tree.gui')) for m in sys.modules); sys.exit(code)"
    result = subprocess.run([sys.executable, "-c", source, "scan", str(folder), "--json", str(target),  # noqa: S603
                             "--folders", str(tmp_path / "folders.csv"), "--largest", str(tmp_path / "files.csv")],
                            capture_output=True, text=True, encoding="utf-8", check=False)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["files"] == 1 and not report["partial"]
    assert report["root"] == str(folder)
    assert report["capacity"]["status"] == "folder_only"
    assert report["capacity"]["unaccounted"] is None
    assert report["capacity"]["omitted_bytes"] is None
    assert json.loads(target.read_text(encoding="utf-8"))["root"]["size"] == 4
    with (tmp_path / "files.csv").open(encoding="utf-8-sig", newline="") as stream:
        assert list(csv.DictReader(stream))[0]["path"] == str(folder / "檔案.txt")


def test_console_comparison_prints_the_biggest_changes(tmp_path: Path, capsys) -> None:
    folder = tmp_path / "scan"
    folder.mkdir()
    (folder / "file").write_bytes(b"old")
    old = tmp_path / "old.json"
    export.export_json(scan(folder).root, old)
    (folder / "file").write_bytes(b"more data")
    assert cli.main(["scan", str(folder), "--compare", str(old)]) == cli.OK
    documents = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert documents[1]["kind"] == "changes"
    assert documents[1]["changes"][0]["change"] == 6


def test_exclusions_produce_partial_coverage_and_exit_one(tmp_path: Path, capsys) -> None:
    (tmp_path / "skipped").mkdir()
    assert cli.main(["scan", str(tmp_path), "--exclude", "skipped"]) == cli.INCOMPLETE
    report = json.loads(capsys.readouterr().out)
    assert report["partial"] and report["coverage"]["skipped_folders"] == 1
    assert report["coverage"]["omitted_bytes"] is None


def test_invalid_scan_or_compare_and_export_failure_return_three(tmp_path: Path, capsys) -> None:
    assert cli.main(["scan", str(tmp_path / "missing")]) == cli.IO_ERROR
    assert json.loads(capsys.readouterr().err)["kind"] == "error"
    (tmp_path / "invalid.json").write_text("{}", encoding="utf-8")
    assert cli.main(["scan", str(tmp_path), "--compare", str(tmp_path / "invalid.json")]) == cli.IO_ERROR
    assert cli.main(["scan", str(tmp_path), "--json", str(tmp_path / "missing" / "tree.json")]) == cli.IO_ERROR


def test_invalid_arguments_exit_two() -> None:
    for arguments in (["scan", ".", "--workers", "0"], ["scan", ".", "--limit", "-1"], []):
        with pytest.raises(SystemExit) as error:
            cli.main(arguments)
        assert error.value.code == cli.INVALID_ARGUMENTS


def test_cancelled_scan_exports_a_partial_snapshot_and_returns_130(tmp_path: Path, monkeypatch, capsys) -> None:
    original = cli.scan

    def cancelled(path, **kwargs):
        event = threading.Event()
        event.set()
        kwargs["cancel"] = event
        return original(path, **kwargs)

    monkeypatch.setattr(cli, "scan", cancelled)
    target = tmp_path / "partial.json"
    assert cli.main(["scan", str(tmp_path), "--json", str(target)]) == cli.INTERRUPTED
    report = json.loads(capsys.readouterr().out)
    assert report["partial"] and report["interrupted"]
    assert json.loads(target.read_text(encoding="utf-8"))["root"]["error"]
