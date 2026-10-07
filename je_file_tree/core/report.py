"""Bounded recorded scan tables and a self-contained, script-free HTML report."""

from __future__ import annotations

import base64
import heapq
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html import escape
import threading
import time

from je_file_tree.core.analysis import Summary, category_stats
from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.export import _atomic_file, _iso_time
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way

Cell = str | int
_LIST_LIMIT = 1000
_TYPE_LIMIT = 10000


class ReportCancelledError(Exception):
    """An explicit cancel event ended preparation or writing before destination replacement."""


@dataclass(frozen=True, slots=True)
class ReportTable:
    """Copied scalar rows, with the complete count when only a bounded prefix is retained."""

    title: str
    header: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]
    count: int


@dataclass(frozen=True, slots=True)
class Report:
    """An immutable, translated snapshot independent of later tree/list mutations."""

    title: str
    note: str
    tables: tuple[ReportTable, ...]


def check_cancel(cancel: threading.Event) -> None:
    """Raise before replacing a requested output when cancellation was observed."""
    if cancel.is_set():
        raise ReportCancelledError()


def _top_folders(root: Node, cancel: threading.Event) -> tuple[list[Node], int]:
    heap, count, stack = [], 0, [root]
    while stack:
        check_cancel(cancel)
        give_way()
        folder = stack.pop()
        if folder is not root:
            count += 1
            item = (folder.size, count, folder)
            if len(heap) < _LIST_LIMIT:
                heapq.heappush(heap, item)
            elif item[:2] > heap[0][:2]:
                heapq.heapreplace(heap, item)
        stack.extend(child for child in folder.children if child.is_dir and not child.is_link)
    return [item[2] for item in sorted(heap, reverse=True)], count


def _entry_rows(nodes: Sequence[Node], cancel: threading.Event) -> tuple[tuple[Cell, ...], ...]:
    rows = []
    for node in nodes:
        check_cancel(cancel)
        rows.append((node.path, node.size, node.allocated, node.file_count if node.is_dir else 1,
                     node.dir_count, _iso_time(node.modified), node.error or ""))
    return tuple(rows)


def prepare_report(root: Node, summary: Summary, labels: Mapping[str, str], *, partial: bool = False,
                   cancel: threading.Event | None = None) -> Report:
    """Copy the whole scan's known summary and bounded lists on a cancellable worker; no file reads."""
    cancel = cancel if cancel is not None else threading.Event()
    check_cancel(cancel)
    coverage = coverage_of(root, cancel=cancel)
    if coverage is None:
        raise ReportCancelledError()
    folders, folder_count = _top_folders(root, cancel)
    fields = ("path", "bytes", "allocated", "files", "folders", "modified", "problem")
    header = tuple(labels[key] for key in fields)
    summary_rows = tuple((labels[key], value) for key, value in (
        ("path", root.path), ("created", _iso_time(time.time())), ("reference", _iso_time(summary.now)),
        ("bytes", root.size), ("allocated", root.allocated), ("files", root.file_count), ("folders", root.dir_count),
        ("coverage", labels["incomplete"] if partial or not coverage.complete else labels["recorded"]),
        ("skipped", coverage.skipped_folders), ("denied", coverage.inaccessible_folders),
        ("pending", coverage.pending_folders), ("note", labels["note"])))
    stat_header = (labels["type"], labels["bytes"], labels["files"])
    tables = [ReportTable(labels["summary"], (labels["field"], labels["value"]), summary_rows, len(summary_rows)),
              ReportTable(labels["top_folders"], header, _entry_rows(folders, cancel), folder_count),
              ReportTable(labels["largest"], header, _entry_rows(summary.largest[:_LIST_LIMIT], cancel),
                          root.file_count)]
    tables.append(ReportTable(labels["types"], stat_header,
                             tuple((stat.extension or labels["no_extension"], stat.size, stat.count)
                                   for stat in summary.extensions[:_TYPE_LIMIT]), len(summary.extensions)))
    categories = category_stats(summary.extensions)
    tables.append(ReportTable(labels["categories"], stat_header,
                             tuple((labels["category_" + stat.category], stat.size, stat.count) for stat in categories),
                             len(categories)))
    tables.append(ReportTable(labels["ages"], (labels["age"], labels["bytes"], labels["files"]),
                             tuple((labels["age_" + stat.age], stat.size, stat.count) for stat in summary.ages),
                             len(summary.ages)))
    check_cancel(cancel)
    return Report(labels["title"], labels["note"], tuple(tables))


def write_html(report: Report, charts: Sequence[tuple[str, bytes]], target: str, *,
               cancel: threading.Event | None = None) -> int:
    """Write escaped scalar tables and inline PNGs atomically, with no scripts or external requests."""
    cancel = cancel if cancel is not None else threading.Event()
    count = 0
    with _atomic_file(target, encoding="utf-8") as stream:
        stream.write('<!doctype html><html><head><meta charset="utf-8">'
                     '<meta name="viewport" content="width=device-width,initial-scale=1">'
                     '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
                     'img-src data:; style-src \'unsafe-inline\'">')
        stream.write(f"<title>{escape(report.title)}</title><style>"
                     "body{font:16px system-ui,sans-serif;margin:2rem;color:#20252d;background:#fff}"
                     "table{border-collapse:collapse;width:100%;font-size:14px}"
                     "th,td{padding:.5rem;border-bottom:1px solid #ddd;text-align:left;overflow-wrap:anywhere}"
                     "th{background:#edf1f7}tr:nth-child(even){background:#f8f9fb}"
                     "figure{margin:1rem 0}img{max-width:100%;height:auto}.table{overflow:auto}"
                     "</style></head><body>")
        stream.write(f"<h1>{escape(report.title)}</h1><p>{escape(report.note)}</p>")
        for table in report.tables:
            check_cancel(cancel)
            stream.write(f"<h2>{escape(table.title)} ({len(table.rows)} / {table.count})</h2>"
                         '<div class="table"><table><thead><tr>')
            stream.write("".join(f"<th>{escape(cell)}</th>" for cell in table.header) + "</tr></thead><tbody>")
            for row in table.rows:
                check_cancel(cancel)
                stream.write("<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>")
                count += 1
            stream.write("</tbody></table></div>")
        for title, png in charts:
            check_cancel(cancel)
            if not png.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Report chart is not a PNG")
            encoded = base64.b64encode(png).decode("ascii")
            stream.write(f'<figure><figcaption>{escape(title)}</figcaption>'
                         f'<img alt="{escape(title, quote=True)}" src="data:image/png;base64,{encoded}"></figure>')
        stream.write("</body></html>\n")
        check_cancel(cancel)
    return count
