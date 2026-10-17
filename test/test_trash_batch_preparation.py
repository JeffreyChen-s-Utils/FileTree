"""Approved batch preparation retains only checked identities without repeated list searches."""

from __future__ import annotations

import threading
from types import SimpleNamespace

from PySide6.QtWidgets import QMessageBox

from je_file_tree.core.cleanup import CleanupGroup, DETAILS
from je_file_tree.core.copy_approval import CopyApproval
from je_file_tree.core.duplicates import DuplicateGroup
from je_file_tree.core.node import Node
from je_file_tree.gui import main_window
from test_gui import window as window  # noqa: PLC0414 - shared owned-window fixture


class _CountedNode(Node):
    comparisons = 0
    __hash__ = object.__hash__

    def __eq__(self, other):
        type(self).comparisons += 1
        return self is other


def _prepare(window, tmp_path, monkeypatch, count=96):
    root = Node(str(tmp_path / "captured"), True, children=[])
    nodes = [_CountedNode(str(i), False, size=10, parent=root) for i in range(count)]
    root.children.extend(nodes)
    window.results.tree_model.set_root(root)
    window._protected = []
    window.results.duplicates._groups = [DuplicateGroup(10, nodes, kept=nodes[0])]
    workers, queued = [], []
    def capture_worker(_root, chosen, _places, _approvals, _parent, *, decisions, audit):
        worker = SimpleNamespace(nodes=list(chosen), decisions=decisions, audit=audit,
                                 done=SimpleNamespace(connect=lambda _callback: None), _cancel=threading.Event())
        workers.append(worker)
        return worker
    monkeypatch.setattr(main_window, "TrashWorker", capture_worker)
    monkeypatch.setattr(main_window, "queue_worker", lambda worker, *_args: queued.append(worker))
    monkeypatch.setattr(window, "_update_actions", lambda: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    return root, nodes, workers, queued


def test_large_duplicate_audit_uses_identity_membership(window, tmp_path, monkeypatch):
    root, nodes, workers, queued = _prepare(window, tmp_path, monkeypatch)
    selected = nodes[1::2]
    _CountedNode.comparisons = 0
    try:
        window.move_to_trash(selected)
        assert len(workers) == 1 and queued == workers
        assert workers[0].nodes == selected
        assert workers[0].decisions == window.results.duplicates.groups
        assert workers[0].audit.reasons == dict.fromkeys(selected, "duplicates")
        assert _CountedNode.comparisons < len(nodes)
        assert root.children == nodes
    finally:
        window._trash_worker = None


def test_copy_approval_is_restricted_after_cleanup_review(window, tmp_path, monkeypatch):
    root, nodes, workers, queued = _prepare(window, tmp_path, monkeypatch)
    proofs = tuple(SimpleNamespace(plan=SimpleNamespace(root=root),
                                   item=SimpleNamespace(node=node, source=node.path, destination="captured-copy"))
                   for node in nodes)
    copies = CopyApproval(proofs, True)
    chosen = list(reversed(nodes[1::2]))
    window.results.cleanup._groups = [CleanupGroup("browser_cache", nodes, 960, DETAILS["browser_cache"])]
    monkeypatch.setattr(window, "_review_cleanup", lambda *_args: chosen)
    questions = []
    monkeypatch.setattr(window, "_confirm_copy_trash", lambda selected, approval:
                        questions.append((list(selected), approval)) or QMessageBox.StandardButton.Yes)
    _CountedNode.comparisons = 0
    try:
        window.move_to_trash(nodes, copies=copies)
        assert len(workers) == 1 and queued == workers
        worker = workers[0]
        assert worker.nodes == chosen and questions == [(chosen, copies)]
        assert worker.decisions == window.results.duplicates.groups
        assert worker.copy_approval.proofs == tuple(proofs[i] for i in range(1, len(nodes), 2))
        assert worker.copy_approval.redirect
        assert worker.audit.reasons == {node: "duplicates" for node in chosen}
        assert _CountedNode.comparisons < len(nodes)
        assert root.children == nodes
    finally:
        window._trash_worker = None


def test_copy_question_keeps_frozen_proof_order_with_one_membership_pass(window, tmp_path, monkeypatch):
    _root, nodes, _workers, _queued = _prepare(window, tmp_path, monkeypatch)
    proofs = tuple(SimpleNamespace(item=SimpleNamespace(node=node, source=node.path,
                                                       destination=f"copied-{i}"))
                   for i, node in enumerate(nodes))
    selected = list(reversed(nodes[1::2]))
    questions = []
    monkeypatch.setattr(QMessageBox, "exec", lambda question: questions.append(
        (question.defaultButton().text(), question.detailedText())) or QMessageBox.StandardButton.No)
    _CountedNode.comparisons = 0
    assert window._confirm_copy_trash(selected, CopyApproval(proofs, True)) == QMessageBox.StandardButton.No
    assert questions == [("&No", "\n\n".join(f"{proofs[i].item.source}\n→ {proofs[i].item.destination}"
                                             for i in range(1, len(nodes), 2)))]
    assert _CountedNode.comparisons < len(nodes)


def test_unrelated_copy_proofs_never_reach_batch_preparation(window, tmp_path, monkeypatch):
    root, nodes, workers, queued = _prepare(window, tmp_path, monkeypatch)
    foreign = Node(root.name, True)
    proof = SimpleNamespace(plan=SimpleNamespace(root=foreign),
                            item=SimpleNamespace(node=nodes[0], source=nodes[0].path))
    try:
        window.move_to_trash([nodes[0]], copies=CopyApproval((proof,)))
        assert not workers and not queued and root.children == nodes
    finally:
        window._trash_worker = None


def test_rejecting_review_never_prepares_or_queues_a_batch(window, tmp_path, monkeypatch):
    root, nodes, workers, queued = _prepare(window, tmp_path, monkeypatch)
    window.results.cleanup._groups = [CleanupGroup("browser_cache", nodes, 960, DETAILS["browser_cache"])]
    monkeypatch.setattr(window, "_review_cleanup", lambda *_args: [])
    questions = []
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: questions.append(1))
    try:
        window.move_to_trash(nodes)
        assert not workers and not queued and not questions and root.children == nodes
    finally:
        window._trash_worker = None
