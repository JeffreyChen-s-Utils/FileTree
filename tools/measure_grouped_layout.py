"""Measure grouped Qt updates on owned in-memory nodes; never scan or change files."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from typing import Any

from PySide6 import __version__ as binding_version
from PySide6.QtCore import QItemSelectionModel, QModelIndex, QPersistentModelIndex, Qt, qVersion
from PySide6.QtWidgets import QApplication, QTreeView

from je_file_tree.core.node import Node
from je_file_tree.gui import grouped_list, i18n
from je_file_tree.gui.tree_model import NODE_ROLE

OPERATIONS = ("noop", "headers", "unit", "labels", "keeper", "language")
_MAX_GROUPS = 1000
_MAX_MEMBERS = 1_000_000
_EVENT_PASSES = 3
_NAME_WIDTH = 317


class _CountedModel(grouped_list.GroupedListModel):
    def __init__(self) -> None:
        super().__init__()
        self.calls = {"index": 0, "flags": 0}

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:  # noqa: B008
        self.calls["index"] += 1
        return super().index(row, column, parent)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        self.calls["flags"] += 1
        return super().flags(index)


@dataclass
class _Capture:
    model: grouped_list.GroupedListModel
    view: QTreeView
    root: Node
    members: tuple[tuple[Node, ...], ...]
    current: QPersistentModelIndex
    selected: Node
    scroll: int
    geometry: dict[str, Any]


def _geometry(view: QTreeView) -> dict[str, Any]:
    return {"view": view.geometry().getRect(), "viewport": view.viewport().geometry().getRect(),
            "header": view.header().geometry().getRect(),
            "columns": [view.columnWidth(column) for column in range(len(grouped_list.COLUMNS))],
            "row_height": view.rowHeight(view.model().index(0, 0))}


def _prepare(app: QApplication, groups: int, members: int, count_calls: bool) -> _Capture:
    root = Node("owned-grouped-layout-probe", True, children=[])
    captured = tuple(tuple(Node(f"{group}-{row:07}", False, size=1536, parent=root)
                           for row in range(members)) for group in range(groups))
    root.children.extend(node for nodes in captured for node in nodes)
    model = _CountedModel() if count_calls else grouped_list.GroupedListModel()
    view = grouped_list.build_view(model)
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    view.resize(1000, 600)
    grouped_list.fill(model, view, [(f"group {row}", nodes) for row, nodes in enumerate(captured)],
                      "auto", keepers=[nodes[0] for nodes in captured])
    view.show()
    for _ in range(_EVENT_PASSES):
        app.processEvents()
    current = model.index(members - 1, 2, model.index(groups - 1, 0))
    view.selectionModel().setCurrentIndex(current, QItemSelectionModel.SelectionFlag.ClearAndSelect
                                         | QItemSelectionModel.SelectionFlag.Rows)
    if groups > 1:
        view.collapse(model.index(0, 0))
    view.setColumnWidth(0, _NAME_WIDTH)
    view.scrollTo(current)
    for _ in range(_EVENT_PASSES):
        app.processEvents()
    return _Capture(model, view, root, captured, QPersistentModelIndex(current), captured[-1][-1],
                    view.verticalScrollBar().value(), _geometry(view))


def _apply(model: grouped_list.GroupedListModel, operation: str, captured: _Capture) -> None:
    if operation in ("headers", "language"):
        i18n.set_language("zh-TW")
    if operation == "headers":
        model.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, len(grouped_list.COLUMNS) - 1)
    elif operation == "unit":
        model.set_unit("MB")
    elif operation == "labels":
        model.set_group_labels([(f"updated group {row}", "updated tip") for row in range(model.rowCount())])
    elif operation == "keeper":
        model.set_group_keeper(len(captured.members) - 1, captured.members[-1][-1])
    elif operation == "language":
        model.retranslate()


def _counts(model: grouped_list.GroupedListModel) -> dict[str, int] | None:
    return dict(model.calls) if isinstance(model, _CountedModel) else None


def _verify(captured: _Capture) -> dict[str, bool]:
    model, view = captured.model, captured.view
    source = tuple(node for nodes in captured.members for node in nodes)
    return {
        "source_preserved": tuple(captured.root.children) == source,
        "all_rows_present": model.rowCount() == len(captured.members) and all(
            model.rowCount(model.index(row, 0)) == len(nodes) for row, nodes in enumerate(captured.members)),
        "member_tuples_preserved": all(group.nodes is nodes for group, nodes in zip(
            model._groups, captured.members, strict=True)),
        "current_preserved": captured.current.isValid() and view.currentIndex() == captured.current,
        "selection_preserved": [index.data(NODE_ROLE) for index in view.selectionModel().selectedRows()]
        == [captured.selected],
        "collapse_preserved": len(captured.members) == 1 or not view.isExpanded(model.index(0, 0)),
        "width_preserved": view.columnWidth(0) == _NAME_WIDTH,
        "scroll_preserved_within_limits": view.verticalScrollBar().value()
        == min(captured.scroll, view.verticalScrollBar().maximum()),
    }


def _validate(operation: str, groups: int, members: int) -> None:
    if operation not in OPERATIONS:
        raise ValueError("Unknown grouped update operation")
    if (type(groups) is not int or type(members) is not int or not 1 <= groups <= _MAX_GROUPS
            or members < 1 or groups * members > _MAX_MEMBERS):
        raise ValueError("Require 1..1000 groups and 1..1000000 total members")


def measure(app: QApplication, operation: str, groups: int = 1000, members: int = 100,
            *, count_calls: bool = True) -> dict[str, Any]:
    """Time one update and three event passes; count callbacks separately from subsequent QA.

    Instrumentation adds Python dispatch overhead. Uninstrumented runs retain the
    ordinary production model/view classes. Event passes are not a frame or input-latency guarantee.
    """
    _validate(operation, groups, members)
    original_language = i18n.current_language()
    i18n.set_language("en")
    captured = _prepare(app, groups, members, count_calls)
    model = captured.model
    notifications = {"headers": 0, "data": 0, "resets": 0}

    def notified(kind: str) -> None:
        notifications[kind] += 1

    model.headerDataChanged.connect(lambda *_: notified("headers"))
    model.dataChanged.connect(lambda *_: notified("data"))
    model.modelReset.connect(lambda: notified("resets"))
    if isinstance(model, _CountedModel):
        model.calls.update(index=0, flags=0)
    try:
        started = time.perf_counter_ns()
        _apply(model, operation, captured)
        handler_ms = (time.perf_counter_ns() - started) / 1_000_000
        handler_calls = _counts(model)
        passes = []
        for number in range(1, _EVENT_PASSES + 1):
            app.processEvents()
            passes.append({"number": number, "cumulative_ms": (time.perf_counter_ns() - started) / 1_000_000,
                           "cumulative_calls": _counts(model)})
        verification = _verify(captured)
        return {"schema": 1, "operation": operation, "groups": groups, "members_per_group": members,
                "members": groups * members, "instrumented": count_calls, "pyside6": binding_version,
                "qt": qVersion(), "platform": app.platformName(), "model_class": type(model).__name__,
                "view_class": type(captured.view).__name__, "handler_ms": handler_ms,
                "handler_calls": handler_calls, "event_passes": passes, "notifications": notifications,
                "geometry_before": captured.geometry, "geometry_after": _geometry(captured.view),
                "headers": [model.headerData(column, Qt.Orientation.Horizontal)
                            for column in range(len(grouped_list.COLUMNS))],
                "sample_size": model.index(0, 1, model.index(0, 0)).data(), "verification": verification,
                "verified": all(verification.values()) and notifications["resets"] == 0}
    finally:
        captured.view.setModel(None)
        captured.view.close()
        i18n.set_language(original_language)


def main() -> int:
    """Run one bounded synthetic update in a fresh process and print its observation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("--groups", type=int, default=1000)
    parser.add_argument("--members", type=int, default=100)
    parser.add_argument("--no-counts", action="store_true", help="Use the ordinary model without callback counters")
    args = parser.parse_args()
    try:
        _validate(args.operation, args.groups, args.members)
    except ValueError as error:
        parser.error(str(error))
    app = QApplication([])
    result = measure(app, args.operation, args.groups, args.members, count_calls=not args.no_counts)
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
