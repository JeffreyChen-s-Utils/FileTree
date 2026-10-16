"""Workspace restart retains each tab's current scan choices independently of saved defaults."""

from dataclasses import replace
import json

from PySide6.QtCore import QSettings
import pytest

from test_gui import _wait
from test_workspace_gui import workspace as workspace  # noqa: PLC0414 - owned teardown
from je_file_tree.gui.app import create_workspace
from je_file_tree.gui.startup_state import workspace_state
from je_file_tree.gui.startup_state import WorkspaceState
from je_file_tree.gui.scan_preferences import SCAN_FLAGS
from je_file_tree.core.scanner import ScanOptions


def test_restart_does_not_replace_distinct_tab_choices_with_saved_values(workspace, qapp, tmp_path):
    first, second = workspace.current, workspace.add_tab()
    first._actions["hidden"].setChecked(False)
    first._actions["capture_file_times"].setChecked(True)
    second._actions["hidden"].setChecked(True)
    second._actions["capture_file_times"].setChecked(False)
    workspace.settings.setValue("scan_workers", 3)
    workspace.settings.setValue("exclusions", ["cache", "*.private"])
    expected = [window._scan_options() for window in (first, second)]
    request = workspace_state(workspace.restart_arguments())
    assert request is not None
    settings = QSettings(str(tmp_path / "new-process.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "en")
    settings.setValue("include_hidden", True)
    settings.setValue("scan_workers", 1)
    settings.setValue("exclusions", ["different"])
    restored = create_workspace(settings)
    try:
        request.restore(restored)
        assert [window._scan_options() for window in restored.operations.windows] == expected
    finally:
        restored.quit_application()
        _wait(qapp, lambda: restored._close_ready)
        restored.deleteLater()


def _payload(options):
    return WorkspaceState((None,) * len(options), options=options).arguments()[0]


def test_all_tab_flags_roundtrip_and_shared_defaults_are_encoded_once():
    first = ScanOptions(include_hidden=False, workers=3, exclude=("cache", "private"), gentle=True,
                        file_times=True, windows_owners=True, exact_windows_allocation=True, count_hard_links=True)
    second = replace(first, include_hidden=True, gentle=False, file_times=False, windows_owners=False,
                     exact_windows_allocation=False, count_hard_links=False)
    state = WorkspaceState((None, ("root",)), 1, (first, second))
    argument = state.arguments()[0]
    assert workspace_state([argument]) == state
    value = json.loads(argument.split("=", 1)[1])
    assert value["version"] == 2
    assert value["defaults"] == {"workers": 3, "exclude": ["cache", "private"]}
    assert all(set(row) == {field for _action, field in SCAN_FLAGS} for row in value["options"])


def test_handoff_refuses_misaligned_counts_or_disagreeing_workspace_defaults():
    with pytest.raises(ValueError):
        WorkspaceState((None, None), options=(ScanOptions(),))
    with pytest.raises(ValueError):
        WorkspaceState((None, None), options=(ScanOptions(workers=1), ScanOptions(workers=2)))
    with pytest.raises(ValueError):
        WorkspaceState((None, None), options=(ScanOptions(), ScanOptions(exclude=("different",))))


def test_captured_choices_are_independent_of_later_ui_changes(workspace):
    first = workspace.current
    first._actions["hidden"].setChecked(False)
    before = first._scan_options()
    arguments = workspace.restart_arguments()
    first._actions["hidden"].setChecked(True)
    workspace.settings.setValue("scan_workers", 7)
    assert workspace_state(arguments).options == (before,)


@pytest.mark.parametrize("field,value", [
    ("workers", 0), ("workers", 33), ("workers", True), ("workers", "3"),
    ("exclude", ["cache"]), ("exclude", ("null\0pattern",)), ("exclude", (True,)),
    ("include_hidden", 1), ("gentle", "true"), ("file_times", None),
    ("windows_owners", 0), ("exact_windows_allocation", "false"), ("count_hard_links", []),
    ("experimental_mft", True),
])
def test_invalid_or_private_options_are_never_exported(field, value):
    with pytest.raises(ValueError):
        WorkspaceState((None,), options=(replace(ScanOptions(), **{field: value}),))


@pytest.mark.parametrize("mutation", ["count", "defaults_extra", "workers", "exclude", "flag_type",
                                       "flag_missing", "private_backend", "approval", "default_conflict"])
def test_invalid_option_metadata_is_refused_before_use(mutation):
    value = json.loads(_payload((ScanOptions(),)).split("=", 1)[1])
    if mutation == "count":
        value["options"].append(dict(value["options"][0]))
    elif mutation == "defaults_extra":
        value["defaults"]["extra"] = True
    elif mutation == "workers":
        value["defaults"]["workers"] = True
    elif mutation == "exclude":
        value["defaults"]["exclude"] = "cache"
    elif mutation == "flag_type":
        value["options"][0]["include_hidden"] = 1
    elif mutation == "flag_missing":
        value["options"][0].pop("gentle")
    elif mutation == "private_backend":
        value["options"][0]["experimental_mft"] = True
    elif mutation == "approval":
        value["approval"] = True
    else:
        value["options"][0]["workers"] = 2
    with pytest.raises(ValueError):
        workspace_state(["--restore-workspace=" + json.dumps(value)])


def test_restore_is_transient_and_explicit_edits_update_shared_runtime_defaults(workspace, qapp, monkeypatch, tmp_path):
    from je_file_tree.gui import main_window
    from PySide6.QtWidgets import QDialog

    settings = QSettings(str(tmp_path / "imported.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "en")
    settings.setValue("include_hidden", True)
    settings.setValue("capture_file_times", False)
    settings.setValue("scan_workers", 1)
    settings.setValue("exclusions", ["saved"])
    restored = create_workspace(settings)
    first = ScanOptions(include_hidden=False, file_times=True, workers=3, exclude=("imported",))
    second = replace(first, include_hidden=True, file_times=False)
    try:
        WorkspaceState((None, None), options=(first, second)).restore(restored)
        assert [window._scan_options() for window in restored.operations.windows] == [first, second]
        assert settings.value("include_hidden") is True
        assert settings.value("capture_file_times") is False
        assert settings.value("scan_workers") == 1 and settings.value("exclusions") == ["saved"]
        extra = restored.add_tab()
        assert extra._scan_options().workers == 3 and extra.exclusions() == ["imported"]
        monkeypatch.setattr(main_window.QInputDialog, "getInt", lambda *_args: (7, True))
        restored.current.configure_workers()

        class Editor:
            def __init__(self, patterns, parent):
                assert patterns == ["imported"]

            def exec(self):
                return QDialog.DialogCode.Accepted

            def patterns(self):
                return ["changed"]

        monkeypatch.setattr(main_window, "ExclusionsDialog", Editor)
        restored.current.edit_exclusions()
        assert all(window._scan_options().workers == 7 and window.exclusions() == ["changed"]
                   for window in restored.operations.windows)
        assert settings.value("scan_workers") == 7 and settings.value("exclusions") == ["changed"]
        restored.quit_application()
        _wait(qapp, lambda: restored._close_ready)
        assert settings.value("include_hidden") is True and settings.value("capture_file_times") is False
    finally:
        restored.quit_application()
        _wait(qapp, lambda: restored._close_ready)
        restored.deleteLater()


def test_restored_workers_receive_immutable_options_with_owned_source_coverage(workspace, qapp, monkeypatch, tmp_path):
    from je_file_tree.gui import scan_worker

    root = tmp_path / "source"
    root.mkdir()
    (root / "kept.bin").write_bytes(b"unchanged")
    skipped = root / "cache"
    skipped.mkdir()
    (skipped / "skipped.bin").write_bytes(b"also unchanged")
    first = ScanOptions(workers=2, exclude=("cache",), gentle=True, file_times=True, count_hard_links=True)
    second = replace(first, file_times=False, include_hidden=False)
    observed = []
    original = scan_worker.ScanWorker.__init__

    def capture(self, path, options, *args, **kwargs):
        observed.append(options)
        original(self, path, options, *args, **kwargs)

    monkeypatch.setattr(scan_worker.ScanWorker, "__init__", capture)
    WorkspaceState((str(root), (str(root),)), options=(first, second)).restore(workspace)
    assert observed == [first, second]
    workspace._scan_defaults.workers = 4
    _wait(qapp, lambda: all(window._worker is None for window in workspace.operations.windows))
    assert observed == [first, second] and all(item.workers == 2 for item in observed)
    assert (root / "kept.bin").read_bytes() == b"unchanged"
    assert (skipped / "skipped.bin").read_bytes() == b"also unchanged"
    for window in workspace.operations.windows:
        files = [node.name for node in window.results.outcome.result.root.iter_files()]
        assert "kept.bin" in files and "skipped.bin" not in files
