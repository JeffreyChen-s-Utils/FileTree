"""Administrator restart retains explicit scan scopes rather than a single display path."""

from test_elevation import window as window  # noqa: PLC0414 - isolated integration fixture
from je_file_tree.gui import elevation
from je_file_tree.gui.startup_state import WorkspaceState, workspace_state
from test_workspace_gui import workspace as workspace  # noqa: PLC0414 - owned workspace teardown


def test_combined_scan_restart_does_not_lose_its_roots(window, monkeypatch, tmp_path):
    requested = []
    roots = (str(tmp_path / "來源甲"), str(tmp_path / "來源乙"))
    window._last_roots, window._last_path = roots, ""
    monkeypatch.setattr(elevation, "relaunch_elevated", lambda arguments: requested.append(list(arguments)) or False)
    window.restart_as_admin()
    assert requested and requested[0], "combined-root restart discarded its entire scan scope"
    assert workspace_state(requested[0]) == WorkspaceState((roots,))


def test_restart_captures_visual_tab_order_and_active_combined_scope(workspace, monkeypatch, tmp_path):
    first = workspace.current
    second, empty = workspace.add_tab(), workspace.add_tab()
    first._last_path = str(tmp_path / "single")
    second._last_roots = (str(tmp_path / "two"), str(tmp_path / "three"))
    workspace.tabs.tabBar().moveTab(2, 0)
    workspace.tabs.setCurrentWidget(second)
    requested = []
    monkeypatch.setattr(elevation, "relaunch_elevated", lambda arguments: requested.append(list(arguments)) or False)
    second.restart_as_admin()
    assert workspace_state(requested[0]) == WorkspaceState((None, first._last_path, second._last_roots), 2)
    assert workspace.tabs.widget(0) is empty and not workspace._closing


def test_closing_tabs_are_excluded_from_restart(workspace):
    first, closing = workspace.current, workspace.add_tab()
    first._last_path = "retained"
    closing._last_roots, closing._closing = ("closing root",), True
    workspace.tabs.setCurrentWidget(first)
    try:
        assert workspace.restart_arguments() == ["retained"]
    finally:
        closing._closing = False


def test_invalid_scope_refuses_launch_without_closing(window, monkeypatch):
    requested = []
    window._last_roots = ("invalid\0root",)
    monkeypatch.setattr(elevation, "relaunch_elevated", lambda arguments: requested.append(arguments) or True)
    window.restart_as_admin()
    assert not requested and not window._settings_dialogs and not window._closing
    assert "Invalid workspace restart" in window.statusBar().currentMessage()
