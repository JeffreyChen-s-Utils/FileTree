"""Native Shell ABI/lifetime and exact undo guards use only freshly owned mocked bin fixtures."""

from contextlib import contextmanager
import ctypes
import os
from types import SimpleNamespace
import threading
import uuid

import pytest

from je_file_tree.core import recycle_shell as shell
from je_file_tree.core import windows_restore as undo
from je_file_tree.core.snapshot import stat_snapshot
from je_file_tree.core.trash_restore import capture_origin


def test_native_guid_property_and_command_layouts_preserve_fixed_windows_widths():
    value = uuid.UUID(shell._RECYCLE)
    assert bytes(shell._guid(str(value))) == value.bytes_le
    assert ctypes.sizeof(shell._Guid) == 16 and ctypes.sizeof(shell._Key) == 20
    assert shell._Command.verb.offset == 2 * ctypes.sizeof(ctypes.c_void_p)
    assert ctypes.sizeof(shell._Command) == (56 if ctypes.sizeof(ctypes.c_void_p) == 8 else 36)
    with pytest.raises(OSError, match="0xffffffff"):
        shell._check(-1)


def _shell_fixture(monkeypatch, matches):
    events, queue = [], list(matches)

    def get_folder(*args):
        args[-1]._obj.value = 1
        return 0

    ole = SimpleNamespace(CoInitializeEx=lambda *_: events.append("init") or 0,
                          CoUninitialize=lambda: events.append("uninit"))
    libraries = (ole, SimpleNamespace(SHGetKnownFolderItem=get_folder), None)
    monkeypatch.setattr(shell, "_libraries", lambda: libraries)
    monkeypatch.setattr(shell, "_bound", lambda *_: ctypes.c_void_p(2))
    monkeypatch.setattr(shell, "_matching", lambda pointer, *_: matches[pointer.value])

    def call(pointer, slot, _types, values):
        events.append((pointer.value, slot))
        if pointer.value == 2 and slot == 3:
            if not queue:
                return 1
            values[1]._obj.value, values[2]._obj.value = queue.pop(0), 1
        return 0

    monkeypatch.setattr(shell, "_call", call)
    return events


def test_unique_shell_match_releases_every_reference_on_success_and_caller_failure(monkeypatch):
    events = _shell_fixture(monkeypatch, {3: None, 4: "actual-payload"})
    with pytest.raises(ValueError, match="owned failure"), shell.recycle_item(SimpleNamespace(path="original")) as item:
        assert item.trashed == "actual-payload" and item.handle.value == 4
        raise ValueError("owned failure")
    assert events.count((1, 2)) == events.count((2, 2)) == events.count((3, 2)) == 1
    assert events.count((4, 2)) == 2 and events.count((4, 1)) == 1 and events[-1] == "uninit"


def test_ambiguous_shell_identity_and_cancellation_never_invoke_restore(monkeypatch):
    events = _shell_fixture(monkeypatch, {3: "first", 4: "second"})
    with pytest.raises(ValueError, match="ambiguous"), shell.recycle_item(None):
        pytest.fail("ambiguous identity cannot publish a selected item")
    assert events.count((3, 2)) == 2 and events.count((4, 2)) == 1 and events[-1] == "uninit"
    events = _shell_fixture(monkeypatch, {})
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ValueError, match="canceled"), shell.recycle_item(None, cancel=cancel):
        pytest.fail("canceled lookup cannot publish an item")
    assert events[-1] == "uninit" and events.count((1, 2)) == events.count((2, 2)) == 1


def test_shell_strings_are_freed_even_on_hresult_failure(monkeypatch):
    buffer = ctypes.create_unicode_buffer("owned 中文 property")
    address, freed = ctypes.cast(buffer, ctypes.c_void_p).value, []

    def failed(_pointer, _slot, _types, values):
        values[-1]._obj.value = address
        return -1

    monkeypatch.setattr(shell, "_call", failed)
    with pytest.raises(OSError):
        ole = SimpleNamespace(CoTaskMemFree=lambda p: freed.append(p.value))
        shell._text(ctypes.c_void_p(1), 5, 0, ctypes.c_uint32, ole)
    assert freed == [address]


def test_canonical_undelete_uses_only_fixed_verb_sync_flag_and_releases_menu(monkeypatch):
    commands, destroyed = [], []

    class Function:
        def __init__(self, callback):
            self.callback = callback
        def __call__(self, *args):
            return self.callback(*args)

    user = SimpleNamespace(CreatePopupMenu=Function(lambda: 42),
                           DestroyMenu=Function(lambda menu: destroyed.append(menu) or 1))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: user, raising=False)
    monkeypatch.setattr(shell, "_bound", lambda *_: ctypes.c_void_p(7))

    def call(_pointer, slot, _types, values):
        if slot == 4:
            command = values[0]._obj
            commands.append((command.mask, command.verb, command.parameters, command.directory, command.window))
        return 0

    monkeypatch.setattr(shell, "_call", call)
    shell.RecycleItem(ctypes.c_void_p(1), "owned-bin", "original").undelete(window=123)
    assert commands == [(0x100, b"undelete", None, None, 123)] and destroyed == [42]


def _fixture(tmp_path, monkeypatch, callback=None):
    root = tmp_path.resolve()
    original = root / "original"
    (original / "empty").mkdir(parents=True)
    (original / "file").write_bytes(b"original bytes")
    origin = capture_origin(str(original), stat_snapshot(str(original)))
    parent = root / "$Recycle.Bin" / "S-1-owned-fixture"
    parent.mkdir(parents=True)
    payload, receipt = parent / "$Rpayload", parent / "$Ipayload"
    original.rename(payload)
    receipt.write_bytes(b"owned mocked receipt")
    calls = []

    def undelete(**_kwargs):
        calls.append("restore")
        if callback is not None:
            callback(original, payload, receipt)
        else:
            os.rename(payload, original)
            receipt.unlink()  # Only this freshly created fixture metadata.

    @contextmanager
    def selected(*_args, **_kwargs):
        yield SimpleNamespace(trashed=str(payload), undelete=undelete)

    monkeypatch.setattr(undo, "recycle_item", selected)
    plan = undo.prepare_windows_restore(origin, actual=str(payload))
    return plan, original, payload, receipt, calls


def test_owned_shell_restore_observes_actual_identity_and_empty_folder(tmp_path, monkeypatch):
    plan, original, payload, receipt, calls = _fixture(tmp_path, monkeypatch)
    result = undo.restore_windows(plan)
    assert result.restored and not result.error and not result.receipt_retained and calls == ["restore"]
    assert (original / "file").read_bytes() == b"original bytes" and (original / "empty").is_dir()
    assert not payload.exists() and not receipt.exists()


@pytest.mark.parametrize("change", ["payload", "receipt", "collision", "cancel"])
def test_changed_payload_receipt_collision_and_cancel_never_invoke_shell(tmp_path, monkeypatch, change):
    plan, original, payload, receipt, calls = _fixture(tmp_path, monkeypatch)
    cancel = threading.Event()
    if change == "payload":
        (payload / "file").write_bytes(b"changed bytes")
    elif change == "receipt":
        receipt.write_bytes(b"modified receipt")
    elif change == "collision":
        original.mkdir()
        (original / "arrival").write_bytes(b"preserved")
    else:
        cancel.set()
    result = undo.restore_windows(plan, cancel=cancel)
    assert not result.restored and result.error and not calls and payload.is_dir() and receipt.exists()
    if change == "collision":
        assert (original / "arrival").read_bytes() == b"preserved"


def test_error_after_native_restore_is_truthful_and_retains_metadata(tmp_path, monkeypatch):
    def partial(original, payload, _receipt):
        os.rename(payload, original)
        (original / "file").write_bytes(b"modified restored bytes")
        raise OSError("owned post-restore error")

    plan, original, payload, receipt, calls = _fixture(tmp_path, monkeypatch, partial)
    result = undo.restore_windows(plan)
    assert result.restored and result.receipt_retained and "post-restore error" in result.error
    assert "observations changed" in result.error and calls == ["restore"]
    assert (original / "file").read_bytes() == b"modified restored bytes" and not payload.exists() and receipt.exists()


def test_unconfirmed_shell_return_is_visible_and_never_claims_success(tmp_path, monkeypatch):
    plan, original, payload, receipt, calls = _fixture(tmp_path, monkeypatch, lambda *_: None)
    monkeypatch.setattr(undo, "_OBSERVE_SECONDS", 0)
    result = undo.restore_windows(plan)
    assert not result.restored and "unconfirmed" in result.error and calls == ["restore"]
    assert not original.exists() and payload.is_dir() and receipt.exists()


def test_delayed_shell_receipt_cleanup_waits_for_completed_native_restore(tmp_path, monkeypatch):
    plan, original, payload, receipt, calls = _fixture(
        tmp_path, monkeypatch, lambda original, payload, _: os.rename(payload, original))
    slept = []

    def complete_cleanup(seconds):
        slept.append(seconds)
        receipt.unlink()  # Only the freshly created fixture metadata; simulates delayed Shell cleanup.

    monkeypatch.setattr(undo.time, "sleep", complete_cleanup)
    result = undo.restore_windows(plan)
    assert slept and calls == ["restore"] and result.restored and not result.error
    assert not result.receipt_retained and original.is_dir() and not payload.exists()


def test_observation_timeout_preserves_confirmed_restore_and_retained_receipt(tmp_path, monkeypatch):
    plan, original, payload, receipt, calls = _fixture(
        tmp_path, monkeypatch, lambda original, payload, _: os.rename(payload, original))
    clock = iter([0, 0, 2])
    monkeypatch.setattr(undo, "_OBSERVE_SECONDS", 1)
    monkeypatch.setattr(undo.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(undo.time, "sleep", lambda _: None)
    result = undo.restore_windows(plan)
    assert result.restored and result.receipt_retained and "receipt" in result.error and calls == ["restore"]
    assert original.is_dir() and not payload.exists() and receipt.exists()
