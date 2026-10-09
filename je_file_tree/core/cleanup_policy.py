"""Validated declarative clean-up settings, separate from scan exclusions."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace

from je_file_tree.core.cleanup import DETAILS, RULES, Rule
from je_file_tree.core.exclusions import Excluded, exclusion_test, is_path
from je_file_tree.core.node import Node

_MAX_AGE = 36500
_MAX_EXCLUSIONS = 1000
_MAX_TEXT = 256_000
_MAX_PATH = 32767


@dataclass(frozen=True, slots=True)
class RuleSetting:
    """One supported rule's enabled state and minimum age in whole days."""

    key: str
    enabled: bool
    minimum_age: int


@dataclass(frozen=True, slots=True)
class CleanupPolicy:
    """Built-in rules with validated overrides; no executable or custom rule content."""

    overrides: tuple[RuleSetting, ...] = ()
    exclusions: tuple[str, ...] = ()
    _excluded: Excluded | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        keys: set[str] = set()
        for setting in self.overrides:
            if (not isinstance(setting, RuleSetting) or setting.key not in DETAILS or setting.key in keys
                    or type(setting.enabled) is not bool or type(setting.minimum_age) is not int
                    or not 0 <= setting.minimum_age <= _MAX_AGE):
                raise ValueError("invalid rule setting")
            keys.add(setting.key)
        if len(self.exclusions) > _MAX_EXCLUSIONS:
            raise ValueError("too many exclusions")
        for path in self.exclusions:
            if not isinstance(path, str) or not path.strip() or "\0" in path or len(path) > _MAX_PATH:
                raise ValueError("invalid exclusion")
            if is_path(path) and not os.path.isabs(path):
                raise ValueError("exclusion paths must be absolute")
        object.__setattr__(self, "_excluded", exclusion_test(self.exclusions))

    def setting(self, key: str) -> RuleSetting:
        """The override or the current built-in default."""
        return next((setting for setting in self.overrides if setting.key == key),
                    RuleSetting(key, True, int(DETAILS[key].minimum_age)))

    def rules(self) -> tuple[Rule, ...]:
        """Built-in recognizers with effective ages; risk/evidence cannot be weakened by settings."""
        return tuple(replace(rule, details=replace(rule.details, minimum_age=self.setting(rule.key).minimum_age))
                     for rule in RULES if self.setting(rule.key).enabled)

    def excludes(self, node: Node) -> bool:
        """Whether this name or exact path must never be proposed, including its descendants."""
        return node.path is not None and self._excluded is not None and self._excluded(node.name, node.path)

    def dumps(self) -> str:
        """Validated JSON suitable for QSettings or an exported policy file."""
        value = {"version": 1, "rules": {setting.key: {"enabled": setting.enabled, "days": setting.minimum_age}
                                         for setting in self.overrides}, "exclusions": list(self.exclusions)}
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def load_policy(text: str) -> CleanupPolicy:
    """Strictly load a bounded policy document; invalid/unknown settings raise ValueError."""
    if not isinstance(text, str) or len(text) > _MAX_TEXT:
        raise ValueError("policy is too large")
    try:
        value = json.loads(text, object_pairs_hook=_unique_object)
    except RecursionError as error:
        raise ValueError("policy nesting is too deep") from error
    if (not isinstance(value, dict) or set(value) != {"version", "rules", "exclusions"}
            or type(value["version"]) is not int or value["version"] != 1
            or not isinstance(value["rules"], dict) or not isinstance(value["exclusions"], list)):
        raise ValueError("invalid policy document")
    settings = []
    for key, setting in value["rules"].items():
        if not isinstance(setting, dict) or set(setting) != {"enabled", "days"}:
            raise ValueError("invalid rule fields")
        settings.append(RuleSetting(key, setting["enabled"], setting["days"]))
    return CleanupPolicy(tuple(settings), tuple(value["exclusions"]))


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate policy keys")
    return result
