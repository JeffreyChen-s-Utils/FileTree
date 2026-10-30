"""Folder trends retain exact bytes and refuse unknown or incompatible observations."""

from datetime import datetime, timedelta, timezone
import threading

import pytest

from je_file_tree.core.history import HistoryCancelledError, ScanHistory
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.core.snapshot import stat_snapshot
from je_file_tree.core.trends import TrendQuery, UnknownReason, normalize_folder, query_trend


def test_known_trend_adjacent_and_direct_contributions(tmp_path):
    root = tmp_path / "source"
    child = root / "child"
    child.mkdir(parents=True)
    (child / "data").write_bytes(b"a" * 10)
    (root / "direct").write_bytes(b"b" * 2)
    store = ScanHistory(tmp_path / "history")
    first = store.save(scan(root).root, options=ScanOptions())
    (child / "data").write_bytes(b"a" * 16)
    (root / "direct").write_bytes(b"b" * 3)
    store.save(scan(root).root, options=ScanOptions())
    (child / "data").write_bytes(b"a" * 11)
    store.save(scan(root).root, options=ScanOptions())
    trend = query_trend(store, TrendQuery(str(root), "child"))
    assert [point.size for point in trend.points] == [10, 16, 11]
    assert [point.change for point in trend.points] == [None, 6, -5]
    assert trend.net == 1
    root_trend = query_trend(store, TrendQuery(str(root)))
    assert root_trend.net == 2
    assert {(row.folder, row.change) for row in root_trend.children} == {("child", 1), ("", 1)}
    assert first.measurement is not None


def test_unknown_missing_legacy_and_pairwise_policy(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    store = ScanHistory(tmp_path / "history")
    store.save(scan(root).root)
    (root / "child").mkdir()
    (root / "child" / "data").write_bytes(b"x")
    store.save(scan(root).root, options=ScanOptions(include_hidden=True))
    store.save(scan(root).root, options=ScanOptions(include_hidden=False))
    store.save(scan(root).root, options=ScanOptions(include_hidden=False))
    trend = query_trend(store, TrendQuery(str(root), "child"))
    assert trend.points[0].reason == UnknownReason.LEGACY
    assert trend.points[1].change is None
    assert trend.points[2].change_reason == UnknownReason.INCOMPATIBLE
    assert trend.points[3].change == 0
    assert trend.net is None
    (root / "child" / "data").unlink()
    (root / "child").rmdir()
    store.save(scan(root).root, options=ScanOptions(include_hidden=False))
    missing = query_trend(store, TrendQuery(str(root), "child"))
    assert missing.points[-1].reason == UnknownReason.MISSING
    assert missing.points[-1].change is None and missing.net is None


def test_period_filter_before_cap_and_inclusive_local_dates(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    store = ScanHistory(tmp_path / "history")
    entries = [store.save(scan(root).root, options=ScanOptions()) for _ in range(3)]
    now = datetime.now(timezone.utc)
    earlier = now - timedelta(days=3)
    later = now + timedelta(days=3)
    for entry, instant in zip(entries, (earlier, now, later), strict=True):
        content = entry.path.read_text(encoding="utf-8")
        entry.path.write_text(content.replace(entry.saved, instant.isoformat(), 1), encoding="utf-8")
    trend = query_trend(store, TrendQuery(str(root), start=now - timedelta(days=1),
                                           end=now + timedelta(days=1), limit=1))
    assert trend.count == 1 and not trend.truncated and len(trend.points) == 1
    capped = query_trend(store, TrendQuery(str(root), limit=2))
    assert capped.count == 3 and capped.truncated and capped.net is None


def test_invalid_paths_and_cancel(tmp_path):
    for path in ("../escape", "/absolute", "\\server\\share", "C:\\drive", "a\0b"):
        with pytest.raises(ValueError):
            normalize_folder(path)
    root = tmp_path / "root"
    root.mkdir()
    store = ScanHistory(tmp_path / "history")
    store.save(scan(root).root, options=ScanOptions())
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(HistoryCancelledError):
        query_trend(store, TrendQuery(str(root)), cancel=cancel)


def test_ambiguous_saved_child_name_is_corrupt_not_a_direct_file(tmp_path):
    root = tmp_path / "root"
    child = root / "child"
    child.mkdir(parents=True)
    (child / "data").write_bytes(b"abc")
    store = ScanHistory(tmp_path / "history")
    entry = store.save(scan(root).root, options=ScanOptions())
    body = entry.path.read_text(encoding="utf-8")
    assert '"name": "child"' in body
    entry.path.write_text(body.replace('"name": "child"', '"name": "a/b"'), encoding="utf-8")
    trend = query_trend(store, TrendQuery(str(root)))
    assert trend.points[0].reason == UnknownReason.CORRUPT
    assert trend.points[0].size is None


def test_unsupported_measurement_keeps_dated_gap(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    data = root / "data"
    store = ScanHistory(tmp_path / "history")
    for size in (2, 5, 8):
        data.write_bytes(b"x" * size)
        entry = store.save(scan(root).root, options=ScanOptions())
        if size == 5:
            body = entry.path.read_text(encoding="utf-8")
            entry.path.write_text(body.replace('"version": 1', '"version": 2', 1), encoding="utf-8")
    trend = query_trend(store, TrendQuery(str(root)))
    assert len(trend.points) == 3 and trend.invalid == 0
    assert [point.size for point in trend.points] == [2, None, 8]
    assert trend.points[1].reason == UnknownReason.INCOMPATIBLE
    assert trend.points[2].change is None and trend.net == 6


def test_incomplete_sibling_and_truncated_body_keep_unknown_points(tmp_path):
    root = tmp_path / "root"
    child = root / "child"
    child.mkdir(parents=True)
    (child / "data").write_bytes(b"xxx")
    store = ScanHistory(tmp_path / "history")
    store.save(scan(root).root, options=ScanOptions())
    partial = scan(root).root
    sibling = Node("failed-file", False, error="access denied", parent=partial)
    partial.children.append(sibling)
    store.save(partial, options=ScanOptions())
    damaged = store.save(scan(root).root, options=ScanOptions())
    body = damaged.path.read_text(encoding="utf-8")
    damaged.path.write_text(body[:-2], encoding="utf-8")
    trend = query_trend(store, TrendQuery(str(root), "child"))
    assert [point.reason for point in trend.points] == [None, UnknownReason.INCOMPLETE, UnknownReason.CORRUPT]
    assert [point.change for point in trend.points] == [None, None, None]
    assert trend.net is None


def test_replaced_root_identity_breaks_pair_without_losing_sizes(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "data").write_bytes(b"x")
    store = ScanHistory(tmp_path / "history")
    store.save(scan(root).root, options=ScanOptions())
    root.rename(tmp_path / "old-root")
    root.mkdir()
    (root / "data").write_bytes(b"xx")
    store.save(scan(root).root, options=ScanOptions())
    trend = query_trend(store, TrendQuery(str(root)))
    assert [point.size for point in trend.points] == [1, 2]
    assert trend.points[-1].change is None and trend.net is None
    assert trend.net_reason == UnknownReason.INCOMPATIBLE


def test_utc_offset_order_and_half_open_interval(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    store = ScanHistory(tmp_path / "history")
    dates = ("2026-01-01T23:30:00+02:00", "2026-01-01T20:00:00-02:00")
    for size, stamp in zip((1, 2), dates, strict=True):
        (root / "data").write_bytes(b"x" * size)
        entry = store.save(scan(root).root, options=ScanOptions())
        body = entry.path.read_text(encoding="utf-8")
        entry.path.write_text(body.replace(entry.saved, stamp, 1), encoding="utf-8")
    trend = query_trend(store, TrendQuery(str(root)))
    assert [point.size for point in trend.points] == [1, 2]
    interval = query_trend(store, TrendQuery(str(root),
                                            start=datetime(2026, 1, 1, 21, 30, tzinfo=timezone.utc),
                                            end=datetime(2026, 1, 1, 22, 0, tzinfo=timezone.utc)))
    assert interval.count == 1 and interval.points[0].size == 1


def test_direct_contribution_cap_reports_total(tmp_path):
    source = tmp_path / "root"
    source.mkdir()
    root = Node(str(source), True, snapshot=stat_snapshot(str(source)), children=[])
    for index in range(1002):
        child = Node(f"child-{index}", True, size=1, parent=root)
        root.children.append(child)
    root.size = len(root.children)
    store = ScanHistory(tmp_path / "history")
    store.save(root, options=ScanOptions())
    store.save(root, options=ScanOptions())
    trend = query_trend(store, TrendQuery(str(source)))
    assert trend.children_count == 1003
    assert len(trend.children) == 1000 and trend.children_truncated


def test_disappearing_direct_child_is_unknown_not_zero(tmp_path):
    root = tmp_path / "root"
    child = root / "child"
    child.mkdir(parents=True)
    (child / "data").write_bytes(b"xx")
    store = ScanHistory(tmp_path / "history")
    store.save(scan(root).root, options=ScanOptions())
    (child / "data").unlink()
    child.rmdir()
    store.save(scan(root).root, options=ScanOptions())
    trend = query_trend(store, TrendQuery(str(root)))
    child_row = next(row for row in trend.children if row.folder == "child")
    assert child_row.before == 2 and child_row.after is None
    assert child_row.change is None and child_row.reason == UnknownReason.MISSING
