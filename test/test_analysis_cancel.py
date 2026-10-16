"""Canceled summaries never publish partial statistics or finish unnecessary passes."""

import threading

import pytest

from je_file_tree.core import analysis
from je_file_tree.core.node import Node


@pytest.mark.parametrize("phase", ["before", "traversal", "largest", "ages"])
def test_summary_cancellation_across_all_passes(monkeypatch, phase):
    root = Node("root", True, children=[])
    for index in range(20):
        child = Node(f"{index}.txt", False, size=index + 1, parent=root)
        root.children.append(child)
    cancel = threading.Event()
    if phase == "before":
        cancel.set()
    else:
        target = {"traversal": "extension_of", "largest": "_file_size", "ages": "age_of"}[phase]
        original = getattr(analysis, target)

        def cancel_during_pass(*args):
            cancel.set()
            return original(*args)

        monkeypatch.setattr(analysis, target, cancel_during_pass)
    with pytest.raises(analysis.AnalysisCancelledError):
        analysis.summarise(root, cancel=cancel)


def test_uncanceled_summary_keeps_complete_totals():
    root = Node("root", True, children=[])
    root.children.append(Node("kept.txt", False, size=12, parent=root))
    expected = analysis.summarise(root, now=100)
    assert analysis.summarise(root, now=100, cancel=threading.Event()) == expected
