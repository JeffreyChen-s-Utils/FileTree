"""Translate the evidence, risk and rebuild instructions attached to clean-up rules."""

from je_file_tree.core.cleanup import DETAILS, RuleDetails
from je_file_tree.gui.i18n import tr


def explanation(key: str, details: RuleDetails | None = None) -> str:
    """Full rule explanation for group tooltips and the review queue."""
    details = details or DETAILS[key]
    return tr("cleanup_evidence", category=tr(f"cleanup_category_{details.category}"),
              days=str(details.minimum_age), risk=tr(f"cleanup_risk_{details.risk}"),
              evidence=tr(f"cleanup_{key}_tip"), rebuild=tr(f"cleanup_rebuild_{details.rebuild}"))
