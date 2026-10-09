"""Explicit verified-copy Trash context and exclusive redirects after a successful OS move."""

from dataclasses import dataclass
from collections.abc import Sequence
import os

if os.name == "nt":
    import _winapi

from je_file_tree.core.copy_io import check_volume
from je_file_tree.core.no_replace import anchored_directory
from je_file_tree.core.node import Node
from je_file_tree.core.verified_copy import CopyProof


@dataclass(frozen=True, slots=True)
class CopyApproval:
    """Frozen copied folders selected for a separate, ordinary protected-folder Trash approval."""

    proofs: tuple[CopyProof, ...]
    redirect: bool = False

    def matches(self, root: Node, nodes: Sequence[Node]) -> bool:
        """Refuse unrelated trees, duplicated proofs or different selected source paths."""
        return (bool(self.proofs) and len({proof.item.node for proof in self.proofs}) == len(self.proofs)
                and all(proof.plan.root is root and proof.item.source == proof.item.node.path
                        for proof in self.proofs)
                and set(nodes) == {proof.item.node for proof in self.proofs})


def redirect_copy(proof: CopyProof) -> None:
    """Create a junction/symlink exclusively at the vacated source; never overwrite or remove arrivals.

    Call only after re-verification and successful approved Trash. Native Windows junction failure
    may retain an empty directory at the source path; report this path and keep the verified copy.
    This is an observed namespace boundary, not a transaction with the operating system's Trash.
    """
    item = proof.item
    with (anchored_directory(item.ancestors) as parent,
          anchored_directory(proof.destination) as destination):
        check_volume(destination, proof.volume)
        if os.path.lexists(item.source):
            raise FileExistsError(item.source)
        if os.name == "nt":
            # CPython CreateJunction uses exclusive CreateDirectoryW; existing paths are refused.
            _winapi.CreateJunction(item.destination, item.source)
        else:
            os.symlink(item.destination, os.path.basename(item.source), target_is_directory=True, dir_fd=parent)
