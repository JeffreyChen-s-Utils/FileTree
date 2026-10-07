"""The scale tool limits a real scan and reports incomplete measurements honestly."""

from argparse import Namespace
from pathlib import Path

from tools import measure_scale


def test_scale_measurement_reports_scan_and_bounded_layouts(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    args = Namespace(root=str(tmp_path), workers=1, memory_mb=4096, seconds=30,
                     duplicates_seconds=0, gui=False)
    report = measure_scale.measure(args)
    assert report["entries"] == 2
    assert report["logical_bytes"] == 5
    assert not report["partial"]
    assert report["json_bytes"] > 0
    assert report["treemap_items"] <= 20000
    assert report["sunburst_items"] <= 5000


def test_scale_memory_budget_returns_partial_tree(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    monkeypatch.setattr(measure_scale, "resident_bytes", lambda: 2 * measure_scale.MB)
    args = Namespace(root=str(tmp_path), workers=1, memory_mb=1, seconds=30,
                     duplicates_seconds=0, gui=False)
    report = measure_scale.measure(args)
    assert report["partial"]
    assert report["stop_reason"] == "memory budget"
