"""Display preferences update captured grouped rows without resetting selections or thumbnails."""

from __future__ import annotations

import io
import threading

import pytest
from PIL import Image
from PySide6.QtCore import QItemSelectionModel, QPersistentModelIndex, Qt

from je_file_tree.core.cleanup import DETAILS, CleanupGroup
from je_file_tree.core.coverage import Coverage
from je_file_tree.core.duplicates import DuplicateGroup, DuplicateResult, DuplicateSavings
from je_file_tree.core.formatting import format_size
from je_file_tree.core.node import Node
from je_file_tree.core.savings import Savings
from je_file_tree.core.similar_photos import SimilarPhotoGroup, SimilarPhotoResult
from je_file_tree.gui import i18n
from je_file_tree.gui import duplicate_savings_worker
from je_file_tree.gui.cleanup_panel import CleanupPanel
from je_file_tree.gui.duplicates_panel import DuplicatesPanel
from je_file_tree.gui.tree_model import NODE_ROLE
from test_gui import _scanned, _wait
from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export


@pytest.fixture(params=["cleanup", "exact", "photos"])
def displayed(request, qapp):
    language = i18n.current_language()
    i18n.set_language("en")
    root = Node("captured", True, children=[])
    members = [[Node(f"{group}-{row:04}", False, size=1536, modified=row, parent=root)
                for row in range(120)] for group in range(3)]
    root.children.extend(node for group in members for node in group)
    panel = CleanupPanel() if request.param == "cleanup" else DuplicatesPanel()
    panel._root = root
    if request.param == "cleanup":
        keys = ["browser_cache", "thumbnails", "temp"]
        panel._groups = [CleanupGroup(key, files, 1536 * len(files), DETAILS[key])
                         for key, files in zip(keys, members, strict=True)]
        panel._coverage = Coverage(1536 * 360, 1, 0, 0, 0, frozenset())
    elif request.param == "exact":
        panel._groups = [DuplicateGroup(1536, list(reversed(files)), kept=files[70]) for files in members]
        panel._found = DuplicateResult(list(panel.groups), 360, 1536 * 360, 0)
        value = Savings(1536 * 119, 4096, 0, 4096, 1000, False)
        panel._savings = DuplicateSavings(value, [value] * 3, [None] * 3)
    else:
        panel.kind.setCurrentIndex(panel.kind.findData("photos"))
        panel._root = root
        thumbnail = io.BytesIO()
        Image.new("RGB", (8, 8), "red").save(thumbnail, format="PNG")
        panel._photos = SimilarPhotoResult([SimilarPhotoGroup(files, [0] * len(files)) for files in members],
                                          360, 0, 4, {members[2][70]: thumbnail.getvalue()})
    panel._rebuild()
    if isinstance(panel, DuplicatesPanel):
        panel._update()
    panel.setAttribute(Qt.WA_DontShowOnScreen)
    panel.resize(900, 600)
    panel.show()
    yield panel, request.param, members
    panel.stop(wait=True)
    panel.close()
    i18n.set_language(language)


@pytest.mark.parametrize("action", ["unit", "language"])
def test_preference_change_preserves_selected_rows_geometry_and_captured_members(displayed, qapp, action):
    panel, kind, members = displayed
    parent = panel.model.index(2, 0)
    current = panel.model.index(70, 2, parent)
    selection = panel.view.selectionModel()
    selection.setCurrentIndex(current, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
    pinned = QPersistentModelIndex(current)
    captured = [group.nodes for group in panel.model._groups]
    icon = panel.model.index(70, 0, parent).data(Qt.DecorationRole)
    panel.view.collapse(panel.model.index(0, 0))
    panel.view.setColumnWidth(0, 317)
    panel.view.scrollTo(current)
    qapp.processEvents()
    scroll = panel.view.verticalScrollBar().value()
    resets = []
    panel.model.modelReset.connect(lambda: resets.append(True))
    if action == "unit":
        panel.set_unit("B")
    else:
        i18n.set_language("zh-TW")
        panel.retranslate()
    qapp.processEvents()
    assert [index.data(NODE_ROLE) for index in selection.selectedRows()] == [members[2][70]]
    assert pinned.isValid() and selection.currentIndex() == pinned and not resets
    assert not panel.view.isExpanded(panel.model.index(0, 0)) and panel.view.isExpanded(parent)
    assert panel.view.columnWidth(0) == 317
    assert panel.view.verticalScrollBar().value() == min(scroll, panel.view.verticalScrollBar().maximum()) > 0
    assert all(group.nodes is original for group, original in zip(panel.model._groups, captured, strict=True))
    assert panel.model.index(70, 1, parent).data() == format_size(1536, panel.unit)
    assert panel.model.headerData(0, Qt.Horizontal) == i18n.tr("column_name")
    _assert_mode_labels(panel, kind, parent, icon)


def _assert_mode_labels(panel, kind, parent, icon):
    current = panel.model.index(70, 0, parent)
    if kind == "exact":
        assert current.data() == i18n.tr("duplicates_kept_name", name=current.data(NODE_ROLE).name)
        assert current.data(Qt.FontRole).bold() and panel.select_extra.isEnabled()
        assert parent.data() == panel._group_title(2, panel.groups[2])
    elif kind == "photos":
        assert current.data(Qt.DecorationRole).cacheKey() == icon.cacheKey()
        assert parent.data() == i18n.tr("photos_group", count="120", distance=4)
        assert parent.data(Qt.ToolTipRole) == i18n.tr("photos_hint")
        assert not panel.view.uniformRowHeights() and panel.view.iconSize().width() == 64
        assert not panel.select_extra.isEnabled() and not panel.link_extra.isEnabled()
    else:
        assert panel.select_group.text() == i18n.tr("cleanup_review_manual")
        assert panel.select_all.isEnabled() and i18n.tr("cleanup_temp") in parent.data()


@pytest.mark.parametrize("displayed", ["photos"], indirect=True)
@pytest.mark.parametrize("action", ["unit", "language"])
def test_photo_refresh_preserves_the_total_member_cap_and_omitted_source_rows(displayed, action):
    panel, _kind, _members = displayed
    files = [Node(str(row), False, size=1536) for row in range(1200)]
    panel._photos = SimilarPhotoResult([SimilarPhotoGroup(files[:600], [0] * 600),
                                       SimilarPhotoGroup(files[600:], [0] * 600)], 1200, 0, 4)
    panel._rebuild()
    if action == "unit":
        panel.set_unit("MB")
    else:
        i18n.set_language("ja")
        panel.retranslate()
    assert panel.model.rowCount() == 2
    assert [panel.model.rowCount(panel.model.index(row, 0)) for row in range(2)] == [600, 400]
    assert panel.model.index(399, 0, panel.model.index(1, 0)).data(NODE_ROLE) is files[999]
    assert not panel.model.index(400, 0, panel.model.index(1, 0)).isValid()
    assert len(panel._photos.groups[1].files) == 600 and not panel.link_groups


@pytest.mark.parametrize("displayed", ["exact"], indirect=True)
@pytest.mark.parametrize("action", ["unit", "language"])
def test_display_change_keeps_the_estimate_worker_and_latest_preferences(displayed, qapp, monkeypatch, action):
    panel, _kind, members = displayed
    started, release = threading.Event(), threading.Event()
    value = panel._savings

    def blocked(*_args, **_kwargs):
        started.set()
        assert release.wait(10)
        return value

    monkeypatch.setattr(duplicate_savings_worker, "estimate_duplicate_savings", blocked)
    monkeypatch.setattr(duplicate_savings_worker, "check_group", lambda *_args, **_kwargs: None)
    current = panel.model.index(70, 0, panel.model.index(2, 0))
    selection = panel.view.selectionModel()
    selection.setCurrentIndex(current, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
    pinned = QPersistentModelIndex(current)
    try:
        panel._start_estimate()
        _wait(qapp, started.is_set)
        worker = panel._estimator
        if action == "unit":
            panel.set_unit("MB")
        else:
            i18n.set_language("ja")
            panel.retranslate()
        assert panel._estimator is worker and panel.running and not worker._cancel.is_set()
        release.set()
        _wait(qapp, lambda: not panel.running)
        assert pinned.isValid() and selection.currentIndex() == pinned
        assert [index.data(NODE_ROLE) for index in selection.selectedRows()] == [members[2][70]]
        assert pinned.data() == i18n.tr("duplicates_kept_name", name=members[2][70].name)
        assert panel.model.index(70, 1, panel.model.index(2, 0)).data() == format_size(1536, panel.unit)
        assert panel.model.index(2, 0).data() == panel._group_title(2, panel.groups[2])
    finally:
        release.set()
        panel.stop(wait=True)


@pytest.mark.parametrize("panel_type", [CleanupPanel, DuplicatesPanel])
def test_empty_panel_preferences_keep_initial_column_geometry_and_reject_invalid_units(qapp, panel_type):
    from PySide6.QtWidgets import QHeaderView

    panel = panel_type()
    try:
        assert [panel.view.columnWidth(column) for column in (0, 1, 3)] == [200, 80, 125]
        assert panel.view.header().sectionResizeMode(2) == QHeaderView.Stretch
        panel.set_unit("MB")
        panel.retranslate()
        with pytest.raises(ValueError, match="unknown size unit"):
            panel.set_unit("invalid")
        assert panel.unit == panel.model._unit == "MB" and panel.model.rowCount() == 0
    finally:
        panel.stop(wait=True)
        panel.close()


@pytest.mark.parametrize("action", ["unit", "language"])
def test_window_preference_entry_points_keep_grouped_selection_after_font_changes(window, qapp, sample_tree, action):
    _scanned(window, qapp, sample_tree)
    cleanup, duplicates = window.results.cleanup, window.results.duplicates
    cleanup.stop(wait=True)
    root = window.results.outcome.result.root
    files = list(root.iter_files())[:2]
    cleanup._groups = [CleanupGroup("temp", files, sum(node.size for node in files), DETAILS["temp"])]
    duplicates._groups = [DuplicateGroup(files[0].size, files, kept=files[0])]
    duplicates._found = DuplicateResult(list(duplicates.groups), 0, 0, 0)
    states = []
    for panel in (cleanup, duplicates):
        panel._rebuild()
        index = panel.model.index(0, 0, panel.model.index(0, 0))
        panel.view.selectionModel().setCurrentIndex(index,
                                                   QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        panel.view.setColumnWidth(0, 317)
        states.append((panel, QPersistentModelIndex(index), panel.model._groups[0].nodes))
    if action == "unit":
        window.set_unit("MB")
    else:
        window.change_language("zh-TW")
    qapp.processEvents()
    for panel, pinned, captured in states:
        selection = panel.view.selectionModel()
        assert pinned.isValid() and selection.currentIndex() == pinned
        assert [index.data(NODE_ROLE) for index in selection.selectedRows()] == [files[0]]
        assert panel.model._groups[0].nodes is captured and panel.view.columnWidth(0) == 317
        assert panel.model.headerData(0, Qt.Horizontal) == i18n.tr("column_name")
        assert panel.model.index(0, 1, panel.model.index(0, 0)).data() == format_size(files[0].size, panel.unit)
    assert cleanup.select_group.text() == i18n.tr("cleanup_review_manual")
    assert duplicates.model.index(0, 0, duplicates.model.index(0, 0)).data() == i18n.tr(
        "duplicates_kept_name", name=files[0].name)
