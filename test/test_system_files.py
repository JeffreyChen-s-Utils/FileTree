"""Windows-managed explanations use anchored namespaces and cannot authorize direct file moves."""

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core import operations
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan
from je_file_tree.core.system_files import SystemFile, system_file
from je_file_tree.gui import main_window as main_module
from je_file_tree.gui import system_files as module
from je_file_tree.gui.scan_worker import analyse

_ENV = {'WINDIR': 'C:\\CustomWindows', 'ProgramData': 'C:\\ProgramData'}


@pytest.mark.parametrize(('path', 'kind', 'tool'), [
    ('C:\\hiberfil.sys', 'hibernate', 'power'), ('D:\\pagefile.sys', 'pagefile', 'memory'),
    ('C:\\swapfile.sys', 'swapfile', 'memory'), ('D:\\WINDOWS.OLD\\Windows\\file', 'old', 'cleanup'),
    ('C:\\$Recycle.Bin\\SID\\file', 'recycle', 'storage'),
    ('D:\\System Volume Information', 'restore', 'restore'),
    ('c:/customwindows/WinSxS/component', 'winsxs', 'cleanup'),
    ('C:\\CustomWindows\\SoftwareDistribution\\Download', 'updates', 'cleanup'),
    ('C:\\ProgramData\\Microsoft\\Windows\\DeliveryOptimization\\Cache', 'delivery', 'cleanup'),
    ('\\\\?\\C:\\CustomWindows\\WinSxS', 'winsxs', 'cleanup'),
])
def test_system_namespaces_cover_descendants_case_and_extended_paths(path, kind, tool) -> None:
    assert system_file(path, platform='win32', environ=_ENV) == SystemFile(kind, tool)


@pytest.mark.parametrize('path', ['C:\\data\\Windows.old', 'C:\\data\\hiberfil.sys', 'D:\\hiberfil.sys',
                                 'C:\\CustomWindows\\WinSxS-copy', 'C:\\data\\$Recycle.Bin',
                                 '\\\\server\\share\\System Volume Information', 'C:pagefile.sys'])
def test_arbitrary_matching_names_other_hibernation_drives_and_unc_do_not_match(path) -> None:
    assert system_file(path, platform='win32', environ=_ENV) is None
    assert system_file(path, platform='linux', environ=_ENV) is None


def test_system_guard_rejects_parent_folders_with_managed_descendants(sample_tree, monkeypatch) -> None:
    root = scan(sample_tree).root
    folder = next(node for node in root.children if node.name == 'photos')
    blocked = folder.children[0].path
    monkeypatch.setattr(operations, 'system_file', lambda path: SystemFile('updates', 'cleanup')
                        if path == blocked else None)
    moved = []
    result = operations.move_batch(root, [folder], lambda path: moved.append(path) or True)
    assert result.skipped == [(folder, 'system_managed')] and moved == []
    assert Path(blocked).is_file()


def test_resolved_managed_alias_is_blocked_even_after_protection_approval(sample_tree, monkeypatch) -> None:
    root = scan(sample_tree).root
    node = next(node for node in root.children if not node.is_dir)
    actual = os.path.join(os.path.dirname(node.path), node.name)
    monkeypatch.setattr(operations, 'system_file', lambda path: SystemFile('winsxs', 'cleanup')
                        if path == actual else None)
    assert operations._check_location(node, root, (), None) == 'system_managed'


def test_gui_rejects_direct_managed_targets_before_confirmation(window, sample_tree, monkeypatch) -> None:
    window.results.show_outcome(analyse(scan(sample_tree)))
    root = window.results.outcome.result.root
    node = next(file for file in root.children if not file.is_dir)
    warnings, questions = [], []
    monkeypatch.setattr(main_module, 'system_file', lambda _path: SystemFile('old', 'cleanup'))
    monkeypatch.setattr(QMessageBox, 'warning', lambda *_args: warnings.append(_args[-1]))
    monkeypatch.setattr(QMessageBox, 'question', lambda *_args: questions.append(True))
    window.move_to_trash([node])
    assert warnings and 'Windows manages this entry' in warnings[0]
    assert questions == [] and window._trash_worker is None and Path(node.path).is_file()


def test_tool_launcher_uses_only_fixed_settings_or_absolute_system_programs(monkeypatch) -> None:
    commands, urls = [], []
    monkeypatch.setattr(module.sys, 'platform', 'win32')
    monkeypatch.setenv('SYSTEMROOT', 'C:\\Windows')
    monkeypatch.setattr(module.subprocess, 'Popen', commands.append)
    monkeypatch.setattr(module.QDesktopServices, 'openUrl', lambda url: urls.append(url.toString()) or True)
    assert module.open_system_tool('cleanup', 'D:\\Windows.old')
    assert commands == [['C:\\Windows\\System32\\cleanmgr.exe', '/d', 'D']]
    assert module.open_system_tool('storage', 'ignored') and urls == ['ms-settings:storagesense']
    assert not module.open_system_tool('anything.exe', 'ignored')
    assert len(commands) == 1


def test_detail_info_retranslates_without_launching_or_reading_files(qapp, monkeypatch) -> None:
    from PySide6.QtWidgets import QWidget

    parent = QWidget()
    panel = module.SystemFileInfo(parent)
    monkeypatch.setattr(module, 'system_file', lambda _path: SystemFile('winsxs', 'cleanup'))
    panel.set_node(Node('C:\\Windows\\WinSxS', True))
    assert 'hard links' in panel.explanation.text() and panel.button.text() == 'Open Disk Cleanup…'
    parent.deleteLater()
