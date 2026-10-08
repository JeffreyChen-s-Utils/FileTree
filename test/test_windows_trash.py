"""Windows recycling vetoes preserve sources and remain separate from filesystem authority."""

from contextlib import contextmanager
from dataclasses import replace
import sys
import threading
from types import SimpleNamespace

import pytest

from je_file_tree.core import windows_trash as recycling
from je_file_tree.core.windows_trash import observed_policy
from je_file_tree.core.scanner import scan
from je_file_tree.core.trash_size import TrashUsage


@pytest.fixture
def source(tmp_path, monkeypatch):
    path = tmp_path / "owned.bin"
    path.write_bytes(b"owned source")
    node = scan(tmp_path).root.children[0]
    monkeypatch.setattr(recycling, "sys", SimpleNamespace(platform="win32"))
    policy = recycling.RecyclePolicy("E:\\", "owned-guid", 49 * 1024 * 1024, False)
    monkeypatch.setattr(recycling, "observed_policy", lambda _path: policy)
    monkeypatch.setattr(recycling, "_windows_usage", lambda _root: TrashUsage(0, 0, True))
    return node, path, policy


def test_passing_observations_keep_the_source_and_do_not_move_it(source):
    node, path, _policy = source
    assert recycling.recycle_reason(node) is None and path.read_bytes() == b"owned source"


@pytest.mark.parametrize("case", ["disabled", "missing", "bin", "changed", "capacity", "size", "coverage"])
def test_disabled_unknown_full_changed_or_incomplete_observations_are_refused(source, monkeypatch, case):
    node, path, policy = source
    expected = "recycle_unverified"
    if case == "disabled":
        monkeypatch.setattr(recycling, "observed_policy", lambda _path: replace(policy, disabled=True))
        expected = "recycle_disabled"
    elif case == "missing":
        def missing(_path):
            raise FileNotFoundError("No observed volume preferences")
        monkeypatch.setattr(recycling, "observed_policy", missing)
    elif case == "bin":
        monkeypatch.setattr(recycling, "_windows_usage", lambda _root: TrashUsage(0, 0, False, "denied"))
    elif case == "changed":
        policies = iter([policy, replace(policy, maximum=policy.maximum * 2)])
        monkeypatch.setattr(recycling, "observed_policy", lambda _path: next(policies))
    elif case == "capacity":
        monkeypatch.setattr(recycling, "_windows_usage", lambda _root: TrashUsage(policy.maximum, 1, True))
        expected = "recycle_capacity"
    elif case == "size":
        node.size += 1
    else:
        node.error = "unreadable"
    assert recycling.recycle_reason(node) == expected and path.read_bytes() == b"owned source"


def test_cancellation_and_pathless_roots_never_query_policy(source, monkeypatch):
    node, _path, _policy = source
    monkeypatch.setattr(recycling, "observed_policy", lambda _path: pytest.fail("Invalid source queried policy"))
    cancel = threading.Event()
    cancel.set()
    assert recycling.recycle_reason(node, cancel) == "cancelled"
    node.snapshot = None
    assert recycling.recycle_reason(node) == "recycle_unverified"


@pytest.mark.parametrize("invalid", [(True, 4), (-1, 4), (1, 1), (2 ** 32, 4), ("49", 4)])
def test_wrong_registry_value_types_are_not_limits(invalid):
    registry = SimpleNamespace(REG_DWORD=4, QueryValueEx=lambda *_args: invalid)
    with pytest.raises(ValueError):
        recycling._dword(registry, object(), "MaxCapacity")


def test_registry_provider_reads_only_fixed_policy_and_verified_volume_keys(source, monkeypatch):
    _node, path, _policy = source
    accesses = []
    @contextmanager
    def opened(hive, key, _reserved, access):
        accesses.append((hive, key, access))
        yield key
    def query(key, name):
        if key == recycling._POLICY_KEY:
            raise FileNotFoundError("absent disabling policy")
        return (49 if name == "MaxCapacity" else 0), 4
    registry = SimpleNamespace(HKEY_CURRENT_USER="user", HKEY_LOCAL_MACHINE="machine", KEY_READ=1,
                               REG_DWORD=4, OpenKey=opened, QueryValueEx=query)
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(recycling, "_volume", lambda _path: ("E:\\", "{owned-guid}"))
    observed = observed_policy(str(path))
    assert observed.maximum == 49 * 1024 * 1024 and not observed.disabled
    assert accesses[-1] == ("user", recycling._VOLUME_KEY + "\\{owned-guid}", 1)
    assert {item[2] for item in accesses} == {registry.KEY_READ}


def test_trash_worker_preserves_source_and_records_capacity_veto_before_qt(qapp, source, tmp_path, monkeypatch):
    from je_file_tree.core.operation_journal import JournalApproval, OperationJournal
    from je_file_tree.gui import trash_worker, file_actions

    node, path, policy = source
    root = node.parent
    monkeypatch.setattr(trash_worker, "recycle_reason", recycling.recycle_reason)
    monkeypatch.setattr(recycling, "_windows_usage", lambda _root: TrashUsage(policy.maximum, 1, True))
    monkeypatch.setattr(file_actions, "trash_receipt", lambda _path: pytest.fail("Vetoed source reached Qt"))
    journal = OperationJournal(tmp_path / "owned-journal")
    worker = trash_worker.TrashWorker(root, [node], [], {}, audit=JournalApproval(journal, {}))
    worker.run()
    assert worker.result.skipped == [(node, "recycle_capacity")]
    assert not worker.result.moved and path.read_bytes() == b"owned source"
    row = journal.recent().records[0]
    assert row.outcome.status == "skipped" and row.outcome.detail == "recycle_capacity"
