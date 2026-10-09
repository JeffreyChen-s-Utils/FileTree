"""Review exclusive cross-volume copies; original Trash remains a separate protected approval."""

from collections.abc import Sequence
from dataclasses import replace
import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QPushButton, QWidget

from je_file_tree.core.copy_approval import CopyApproval
from je_file_tree.core.formatting import format_count
from je_file_tree.core.namespace_moves import NamespacePlan
from je_file_tree.core.node import Node
from je_file_tree.core.snapshot import unpack_snapshot
from je_file_tree.core.verified_copy import CopyResult, copy_folders, prepare_copy
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.namespace_dialog import NamespaceDialog, namespace_reason
from je_file_tree.gui.namespace_worker import NamespaceOperationWorker, NamespacePreviewWorker, NamespaceRequest


class CopyPreviewWorker(NamespacePreviewWorker):
    """Reuse owned preview lifecycle while refusing same-volume pairs in the cross-drive interface."""

    def _prepare(self, request: NamespaceRequest) -> NamespacePlan | None:
        plan = prepare_copy(request.root, request.nodes, request.directory,
                            collision=request.collision, cancel=self.cancel)
        if plan is None:
            return None
        items = tuple(replace(item, reason="same_volume")
                      if not item.reason and unpack_snapshot(item.snapshot).device
                      == unpack_snapshot(item.target_ancestors[-1].snapshot).device else item for item in plan.items)
        return replace(plan, items=items)


class CopyOperationWorker(NamespaceOperationWorker):
    """Copy/verify off-thread and retain partial outcomes before publishing any queued result."""

    file_progress = Signal(str, int, int)

    def _execute(self) -> CopyResult:
        return copy_folders(self.plan, cancel=self.cancel, progress=self.file_progress.emit)

    def _external_parents(self) -> set[str]:
        paths = self.result.partial + [proof.item.destination for proof in self.result.verified]
        return {os.path.dirname(path) for path in paths}


class CopyDialog(NamespaceDialog):
    """Show all literal pairs and preserve originals until explicitly requested ordinary Trash approval."""

    def __init__(self, root: Node, nodes: Sequence[Node], unit: str, parent: QWidget) -> None:
        self.finish_requested = False
        self.approval: CopyApproval | None = None
        self._redirect = False
        super().__init__(root, nodes, unit, parent, rename=False)
        self.setWindowTitle(tr("menu_move_drive"))
        self.hint.setText(tr("copy_hint"))
        self.apply_button.setText(tr("copy_apply"))
        self.redirect = QCheckBox(tr("copy_redirect"))
        self.redirect.setChecked(False)
        self.redirect.toggled.connect(self._invalidate)
        self.finish_button = QPushButton(tr("copy_finish"))
        self.finish_button.setEnabled(False)
        self.finish_button.clicked.connect(self._finish)
        self.layout().insertWidget(3, self.redirect)
        self.layout().insertWidget(self.layout().count() - 1, self.finish_button)

    def _preview_worker(self, request: NamespaceRequest) -> CopyPreviewWorker:
        return CopyPreviewWorker(request, self)

    def _operation_worker(self, plan: NamespacePlan) -> CopyOperationWorker:
        self._redirect = self.redirect.isChecked()
        self.redirect.setEnabled(False)
        worker = CopyOperationWorker(plan, self)
        worker.file_progress.connect(lambda path, done, total: not self._closed and self.status.setText(
            tr("copy_progress", path=path, done=format_count(done), total=format_count(total))))
        return worker

    def _question_text(self, count: int, skipped: int) -> str:
        return tr("copy_confirm", count=format_count(count), skipped=format_count(skipped))

    def _completed(self, result: CopyResult) -> None:
        if self._closed:
            return
        self._reported = True
        self.status.setText(tr("copy_done", copied=format_count(len(result.verified)),
                               skipped=format_count(len(result.skipped)), failed=format_count(len(result.failed)))
                            + ("\n" + tr("scan_cancelled") if result.canceled else ""))
        lines = [f"{item.source}\n→ {item.destination}\n{reason}" for item, reason in result.failed]
        lines += [f"{item.source}\n→ {item.destination}\n{namespace_reason(item)}" for item, _ in result.skipped]
        lines += [tr("copy_partial", path=path) for path in result.partial]
        lines += [tr("namespace_refreshed", path=path, files=format_count(files), errors=format_count(errors))
                  for path, files, errors in self.operation.refreshed]
        lines += [tr("namespace_refresh_failed", path=path, reason=reason)
                  for path, reason in self.operation.refresh_errors]
        self.output.setPlainText("\n\n".join(lines))
        self.output.setVisible(bool(lines))
        if result.verified and not result.failed and not result.canceled:
            self.approval = CopyApproval(tuple(result.verified), self._redirect)
            self.finish_button.setEnabled(True)

    def _finish(self) -> None:
        if self.approval is not None and not self._closed:
            self.finish_requested = True
            self.accept()
