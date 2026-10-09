"""Policies cannot turn excluded data into a whole-folder candidate or executable rule."""

import json
import threading

import pytest

from conftest import make_tree
from test_cleanup import age_tree, home as home_fixture
from je_file_tree.core.cleanup import find_cleanup
from je_file_tree.core.cleanup_policy import CleanupPolicy, RuleSetting, load_policy
from je_file_tree.core.scanner import scan

home = home_fixture


def test_defaults_preserve_rules_and_round_trip(home) -> None:
    root = scan(home).root
    before = find_cleanup(root)
    after = find_cleanup(root, policy=load_policy(CleanupPolicy().dumps()))
    assert before == after
    policy = CleanupPolicy((RuleSetting("temp", False, 60),), (str(home / "Projects"), "*.private"))
    assert load_policy(policy.dumps()) == policy


def test_disable_age_and_excluded_descendant_keep_accounting_unchanged(home) -> None:
    root = scan(home).root
    size = root.size
    excluded = str(home / "AppData/Local/Google/Chrome/User Data/Default/Cache/data_1")
    policy = CleanupPolicy((RuleSetting("temp", False, 7), RuleSetting("old_installers", True, 36500)), (excluded,))
    result = find_cleanup(root, policy=policy)
    assert not {"temp", "old_installers", "browser_cache"} & {group.key for group in result}
    assert root.size == size and (home / "AppData/Local/Temp/setup.tmp").exists()


def test_excluded_ancestor_is_not_traversed_and_cannot_be_selected_as_empty(tmp_path) -> None:
    make_tree(tmp_path, {"keep": {"__pycache__": {"file.pyc": b"compiled"}}, "empty": {"keep": {}}})
    age_tree(tmp_path)
    root = scan(tmp_path).root
    policy = CleanupPolicy(exclusions=("keep",))
    assert find_cleanup(root, policy=policy) == []
    assert find_cleanup(root, policy=CleanupPolicy(exclusions=(str(tmp_path),))) == []


@pytest.mark.parametrize("rules,exclusions", [
    ({"unknown": {"enabled": True, "days": 7}}, []),
    ({"temp": {"enabled": "false", "days": 7}}, []),
    ({"temp": {"enabled": True, "days": True}}, []),
    ({"temp": {"enabled": True, "days": -1}}, []),
    ({"temp": {"enabled": True, "days": 36501}}, []),
    ({"temp": {"enabled": True, "days": 7, "command": "anything"}}, []),
    ({}, ["relative/path"]), ({}, ["bad\0path"]), ({}, [None]),
])
def test_imported_settings_are_strict(rules, exclusions) -> None:
    with pytest.raises(ValueError):
        load_policy(json.dumps({"version": 1, "rules": rules, "exclusions": exclusions}))


@pytest.mark.parametrize("text", ["[]", "{}", "not JSON", "[" * 2000 + "]" * 2000,
                                  '{"version":1,"version":2,"rules":{},"exclusions":[]}'])
def test_corrupt_or_ambiguous_documents_are_rejected(text) -> None:
    with pytest.raises(ValueError):
        load_policy(text)


def test_zero_age_still_rejects_unknown_and_future_dates(home) -> None:
    root = scan(home).root
    for node in root.iter_nodes():
        node.modified = 0
    policy = CleanupPolicy(tuple(RuleSetting(key, True, 0) for key in ("temp", "crash_dumps", "empty_folders")))
    assert find_cleanup(root, policy=policy) == []
    cancel = threading.Event()
    cancel.set()
    assert find_cleanup(root, policy=policy, cancel=cancel) is None
