"""Atomic append, partial batches, crash outcomes, retention and metadata-only exports."""

import os
import subprocess  # nosec B404 - fixed Python test helpers
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from je_file_tree.core import operation_journal as module
from je_file_tree.core.operation_journal import (
    OperationJournal, OperationOutcome, OperationRecord, export_journal, redact_home,
)
from je_file_tree.core.scanner import scan


def record(tmp_path, *, name="source"):
    return OperationRecord(uuid.uuid4().hex, uuid.uuid4().hex, module._now(), str(tmp_path / name),
                           (1, 2), "manual", OperationOutcome("approved"))


def test_approved_and_partial_batch_results_survive_restart_without_file_contents(tmp_path) -> None:
    folder = tmp_path / "scan"
    folder.mkdir()
    content = b"private content must never reach the journal"
    for name in ("one", "two", "three"):
        (folder / name).write_bytes(content)
    root = scan(folder).root
    batch = uuid.uuid4().hex
    records = [OperationRecord.approved(batch, node, "cleanup:temp") for node in root.children]
    path = tmp_path / "journal"
    journal = OperationJournal(path)
    journal.append(records)
    first = next(path.glob("*.jsonl")).read_bytes()
    outcomes = (OperationOutcome("moved", destination=str(tmp_path / "trash")), OperationOutcome("failed"),
                OperationOutcome("skipped", "changed"))
    journal.append([item.finished(outcome) for item, outcome in zip(records, outcomes, strict=True)])
    data = next(path.glob("*.jsonl")).read_bytes()
    assert data.startswith(first) and content not in data
    result = OperationJournal(path).recent()
    assert {item.outcome.status for item in result.records} == {"moved", "failed", "skipped"}
    assert all(item.batch == batch and item.identity is not None for item in result.records)
    assert result.invalid == result.unavailable == 0


def test_atomic_append_failure_preserves_the_previous_complete_file(tmp_path, monkeypatch) -> None:
    journal = OperationJournal(tmp_path)
    original = record(tmp_path)
    journal.append([original])
    path = next(tmp_path.glob("*.jsonl"))
    previous = path.read_bytes()

    def denied(source, target):
        raise OSError("write refused")

    monkeypatch.setattr(module.os, "replace", denied)
    with pytest.raises(OSError):
        journal.append([original.finished(OperationOutcome("moved"))])
    assert path.read_bytes() == previous and journal.recent().records[0].outcome.status == "approved"
    assert not list(tmp_path.glob(".journal-*.tmp"))


def test_crash_after_approval_is_unknown_on_restart_and_lock_is_released(tmp_path) -> None:
    script = """import os, sys
from je_file_tree.core.operation_journal import OperationJournal, OperationRecord, OperationOutcome, _now
journal = OperationJournal(sys.argv[1])
journal.append([OperationRecord('1'*32, '2'*32, _now(), sys.argv[2], None, 'manual', OperationOutcome('approved'))])
os._exit(7)
"""
    result = subprocess.run(  # noqa: S603 - fixed helper; temp paths are argument values
        [sys.executable, "-c", script, str(tmp_path), str(tmp_path / "unmoved")], check=False)
    assert result.returncode == 7
    journal = OperationJournal(tmp_path)
    assert journal.recent().records[0].outcome.status == "approved"
    journal.append([record(tmp_path)])
    assert len(journal.recent().records) == 2


def test_concurrent_writers_do_not_lose_approved_events(tmp_path) -> None:
    records = [record(tmp_path, name=str(index)) for index in range(20)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(OperationJournal(tmp_path).append, records[index::2]) for index in range(2)]
        for future in futures:
            future.result()
    assert {row.id for row in OperationJournal(tmp_path).recent().records} == {row.id for row in records}


def test_retention_only_removes_owned_segments_and_preserves_recent_records(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(module, "_EVENT_BYTES", 1024)
    monkeypatch.setattr(module, "_SEGMENT_BYTES", 1024)
    journal = OperationJournal(tmp_path, max_bytes=1536)
    (tmp_path / "notes.jsonl").write_text("user note", encoding="utf-8")
    old = tmp_path / f"actions-20000101-{uuid.uuid4().hex}.jsonl"
    old.write_bytes(module._encode(record(tmp_path)))
    os.utime(old, (1_600_000_000, 1_600_000_000))
    journal.append([record(tmp_path, name=str(index)) for index in range(10)])
    assert not old.exists() and (tmp_path / "notes.jsonl").read_text(encoding="utf-8") == "user note"
    assert sum(path.stat().st_size for path in tmp_path.glob("actions-*.jsonl")) <= 1536
    assert journal.recent().records


def test_corruption_is_reported_and_unknown_outcomes_are_exported_with_home_redaction(tmp_path) -> None:
    home = tmp_path / "home"
    journal = OperationJournal(tmp_path / "journal")
    approved = record(home)
    destination = str(home / ".Trash/files/file")
    moved = record(home).finished(OperationOutcome("moved", destination=destination))
    journal.append([approved, moved])
    with next(journal.directory.glob("*.jsonl")).open("a", encoding="utf-8") as stream:
        stream.write("corrupted\n")
    result = journal.recent()
    assert result.invalid == 1 and len(result.records) == 2
    output = tmp_path / "report.csv"
    assert export_journal(result.records, output, home=str(home)) == 2
    text = output.read_text(encoding="utf-8-sig")
    assert str(home) not in text and "{HOME}" in text and "unknown" in text
    sibling = str(tmp_path / "home-other/file")
    assert redact_home(sibling, str(home)) == sibling
    assert redact_home(str(home), str(home)) == "{HOME}"


def test_completed_outcome_is_not_overwritten_by_an_older_approval_event(tmp_path) -> None:
    journal = OperationJournal(tmp_path)
    approved = record(tmp_path)
    moved = approved.finished(OperationOutcome("moved"))
    journal.append([moved, replace(approved, timestamp=module._now())])
    assert journal.recent().records[0].outcome.status == "moved"
