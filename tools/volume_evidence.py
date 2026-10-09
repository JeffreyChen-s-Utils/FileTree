"""Scalar validation evidence without copying/serializing live authorization trees."""

from dataclasses import fields

from je_file_tree.core.capacity import CapacityLedger


def ledger_record(ledger: CapacityLedger) -> dict[str, object]:
    """Keep capacity scalars, coverage counts and unknowns; retain only the unsafe-folder count."""
    record = {field.name: getattr(ledger, field.name) for field in fields(ledger) if field.name != "coverage"}
    coverage = {field.name: getattr(ledger.coverage, field.name)
                for field in fields(ledger.coverage) if field.name != "unsafe"}
    coverage["unsafe_folders"] = len(ledger.coverage.unsafe)
    record["coverage"] = coverage
    return record
