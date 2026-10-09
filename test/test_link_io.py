"""Native scoped backup/alias retirement touches only newly created owned duplicate fixtures."""

from dataclasses import replace
import os
import threading
import uuid

import pytest

from test_duplicate_links import _fixture, open_bytes
from je_file_tree.core import duplicate_links, link_io
from je_file_tree.core.snapshot import stat_snapshot


def _published(tmp_path):
    root, group = _fixture(tmp_path)
    plan = duplicate_links.prepare_links(root, [group])
    pair = plan.pairs[0]
    duplicate_links.verify_link_pair(plan, pair)
    temporary = os.path.join(root.path, ".filetree-link-" + uuid.uuid4().hex + ".tmp")
    backup = os.path.join(root.path, ".filetree-copy-" + uuid.uuid4().hex + ".bak")
    os.link(pair.keeper_path, temporary)
    os.rename(pair.copy_path, backup)  # Only freshly created fixture names, with vacant owned targets.
    os.rename(temporary, pair.copy_path)
    return pair, backup, stat_snapshot(backup), stat_snapshot(pair.keeper_path)


def test_native_backup_retirement_fully_verifies_shared_alias_and_preserves_bytes(tmp_path):
    pair, backup, expected, keeper = _published(tmp_path)
    before = open_bytes(backup)
    link_io._retire_backup(pair, backup, expected, keeper, None)
    assert not os.path.exists(backup)
    assert open_bytes(pair.keeper_path) == open_bytes(pair.copy_path) == before
    assert os.stat(pair.keeper_path).st_ino == os.stat(pair.copy_path).st_ino


@pytest.mark.parametrize("change", ["content", "identity", "cancel", "scope"])
def test_changed_unapproved_or_canceled_backup_retirement_keeps_all_payloads(tmp_path, change):
    pair, backup, expected, keeper = _published(tmp_path)
    cancel = threading.Event()
    if change == "content":
        with open(backup, "wb") as stream:
            stream.write(b"changed old payload retained")
        expected = stat_snapshot(backup)
    elif change == "identity":
        retained = backup + ".retained"
        os.rename(backup, retained)
        with open(backup, "wb") as stream:
            stream.write(open_bytes(retained))
        expected = stat_snapshot(backup)
    elif change == "cancel":
        cancel.set()
    else:
        pair = replace(pair, copy_parents=())
    with pytest.raises((OSError, ValueError)):
        link_io._retire_backup(pair, backup, expected, keeper, cancel)
    assert os.path.exists(backup) and os.path.exists(pair.copy_path) and os.path.exists(pair.keeper_path)


def test_temporary_cleanup_requires_created_scoped_alias_and_live_keeper(tmp_path):
    root, group = _fixture(tmp_path)
    pair = duplicate_links.prepare_links(root, [group]).pairs[0]
    alias = os.path.join(root.path, ".filetree-link-" + uuid.uuid4().hex + ".tmp")
    os.link(pair.keeper_path, alias)
    link_io._remove_alias(pair, alias, stat_snapshot(alias))
    assert not os.path.exists(alias) and open_bytes(pair.keeper_path)
    with pytest.raises(ValueError, match="artifact"):
        link_io._remove_alias(pair, pair.copy_path, stat_snapshot(pair.copy_path))
    assert os.path.exists(pair.copy_path)


def test_temporary_alias_that_became_last_name_is_never_deleted(tmp_path):
    root, group = _fixture(tmp_path)
    pair = duplicate_links.prepare_links(root, [group]).pairs[0]
    alias = os.path.join(root.path, ".filetree-link-" + uuid.uuid4().hex + ".tmp")
    os.link(pair.keeper_path, alias)
    os.unlink(pair.keeper_path)  # Only this test's fresh owned fixture; simulates losing the original name.
    with pytest.raises(ValueError, match="last name"):
        link_io._remove_alias(pair, alias, stat_snapshot(alias))
    assert open_bytes(alias), "the only remaining name must keep its owned payload"
