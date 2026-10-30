"""Result guidance stays bounded and reuses existing navigation and worker results."""

import dataclasses

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import pytest

from test_gui import _wait, window as window  # noqa: PLC0414 - shared fixture
from je_file_tree.core.analysis import summarise
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan
from je_file_tree.gui import i18n
from je_file_tree.gui.results_view import CLEANUP_TAB, PROBLEMS_TAB
from je_file_tree.gui.scan_worker import analyse


def test_summary_top_folders_are_direct_nonlinked_and_bounded():
    root = Node("root", True, children=[])
    for index in range(5):
        folder = Node(str(index), True, size=index, parent=root, children=[])
        folder.children.append(Node("nested", True, size=999, parent=folder))
        root.children.append(folder)
    root.children.append(Node("huge", False, size=99999, parent=root))
    root.children.append(Node("link", True, size=99999, is_link=True, parent=root))
    assert [node.name for node in summarise(root).top_folders] == ["4", "3", "2"]


@pytest.mark.parametrize("language", i18n.LANGUAGES)
def test_highlights_navigate_and_retranslate_without_selection_loss(window, sample_tree, qapp, language):
    results = window.results
    results.show_outcome(analyse(scan(sample_tree)))
    highlights = results.highlights
    _wait(qapp, lambda: results.cleanup.proposal_summary is not None)
    i18n.set_language(language)
    results.retranslate()
    folder = results.outcome.top_folders[0]
    highlights.folders[0].click()
    assert results.selected_node() is folder
    selected = results.tree.currentIndex()
    results.set_unit("KB")
    assert results.tree.currentIndex() == selected
    assert highlights.toggle.text() == i18n.tr("highlights_title")
    assert highlights.cleanup.text() != i18n.tr("highlights_cleanup_waiting")
    highlights.cleanup.click()
    assert results.tabs.currentIndex() == CLEANUP_TAB
    highlights.problems.click()
    assert results.tabs.currentIndex() == PROBLEMS_TAB
    QTest.keyClick(highlights.toggle, Qt.Key.Key_Space)
    assert highlights.body.isHidden()
    results.retranslate()
    assert highlights.body.isHidden() and results.selected_node() is folder


def test_highlights_distinguish_pending_empty_and_partial(window, sample_tree):
    results = window.results
    highlights = results.highlights
    results.begin_scan()
    assert highlights.message.text() == i18n.tr("highlights_waiting")
    assert highlights.cleanup.text() == i18n.tr("highlights_cleanup_waiting")
    assert not highlights.cleanup.isEnabled()
    outcome = analyse(scan(sample_tree))
    results.show_outcome(dataclasses.replace(outcome, partial=True))
    assert highlights.message.text() == i18n.tr("highlights_partial")
    highlights.show_cleanup((0, 0))
    assert highlights.cleanup.text() != i18n.tr("highlights_cleanup_waiting")
    results.begin_scan()
    assert all(button.isHidden() for button in highlights.folders)


def test_refreshed_capacity_replaces_unknown_coverage_without_reselection(window, sample_tree):
    outcome = analyse(scan(sample_tree))
    results = window.results
    results.show_outcome(outcome)
    results.select_node(outcome.top_folders[0])
    selected = results.selected_node()
    results.clear_capacity()
    assert results.highlights.problems.text() == i18n.tr("highlights_coverage_unknown")
    results.set_capacity(outcome.capacity)
    assert results.highlights.problems.text() != i18n.tr("highlights_coverage_unknown")
    assert results.selected_node() is selected


def test_highlights_use_captured_data_without_disk_or_child_iteration(window, sample_tree, monkeypatch, qapp):
    outcome = analyse(scan(sample_tree))
    window.results.show_outcome(outcome)
    _wait(qapp, lambda: window.results.cleanup.proposal_summary is not None)
    class Unreadable(list):
        def __iter__(self):
            pytest.fail("GUI iterated the tree")
    children = outcome.result.root.children
    outcome.result.root.children = Unreadable(children)
    try:
        with monkeypatch.context() as context:
            context.setattr("os.lstat", lambda *_args, **_kwargs: pytest.fail("GUI queried storage"))
            window.results._update_overview()
            window.results.highlights.retranslate()
    finally:
        outcome.result.root.children = children
