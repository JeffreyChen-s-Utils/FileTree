"""MSI metadata uses read-only database handles and fixed parameterized queries, never install sessions."""

from types import SimpleNamespace

import pytest

from tools import msi_metadata as reader


def _api(monkeypatch, failure=""):
    acquired, closed, queries, cursor_closed, modes = [], [], [], [], []
    names, current = {}, {}
    def acquire(pointer):
        pointer._obj.value = len(acquired) + 1
        acquired.append(pointer._obj.value)
        return 0
    def open_database(_path, mode, pointer):
        modes.append(mode)
        return acquire(pointer)
    def open_view(_database, query, pointer):
        queries.append(query)
        return acquire(pointer)
    def parameter(_count):
        acquired.append(len(acquired) + 1)
        return acquired[-1]
    def set_string(handle, _index, name):
        names[handle] = name
        return 1 if failure == "parameter" else 0
    def execute(view, parameters):
        current["name"] = names[parameters]
        current["view"] = view
        return 1 if failure == "execute" else 0
    def fetch(view, pointer):
        assert view == current["view"]
        return acquire(pointer)
    def string(_record, _index, buffer, _length):
        buffer.value = current["name"]
        return 234 if failure == "string" else 0
    def summary(_database, path, updates, pointer):
        assert path is None and updates == 0
        return acquire(pointer)
    def template(_summary, property_id, kind, _number, date, buffer, _length):
        assert property_id == 7 and date is None
        kind._obj.value = 30
        buffer.value = "x64;1033"
        return 1 if failure == "summary" else 0
    def close(handle):
        closed.append(handle)
        return 1 if failure == "close" else 0
    def close_cursor(view):
        cursor_closed.append(view)
        return 0
    api = SimpleNamespace(MsiOpenDatabaseW=open_database, MsiDatabaseOpenViewW=open_view,
                          MsiCreateRecord=parameter, MsiRecordSetStringW=set_string, MsiViewExecute=execute,
                          MsiViewFetch=fetch, MsiRecordGetStringW=string, MsiGetSummaryInformationW=summary,
                          MsiSummaryInfoGetPropertyW=template, MsiViewClose=close_cursor, MsiCloseHandle=close)
    monkeypatch.setattr(reader, "_kernel", lambda: api)
    return acquired, closed, queries, cursor_closed, modes


def test_metadata_reads_fixed_properties_with_parameter_records_and_closes_every_handle(tmp_path, monkeypatch):
    acquired, closed, queries, cursors, modes = _api(monkeypatch)
    properties = reader.read_properties(tmp_path / "owned.msi")
    assert properties == {**{name: name for name in reader._PROPERTIES}, "Template": "x64;1033"}
    assert modes == [None]
    assert queries == ["SELECT `Value` FROM `Property` WHERE `Property` = ?"] * 6
    assert len(cursors) == 6 and sorted(closed) == acquired and len(closed) == len(set(closed))


@pytest.mark.parametrize("failure", ["parameter", "execute", "string", "summary", "close"])
def test_native_errors_remain_visible_and_release_all_created_handles(tmp_path, monkeypatch, failure):
    acquired, closed, _queries, _cursors, _modes = _api(monkeypatch, failure)
    with pytest.raises(OSError):
        reader.read_properties(tmp_path / "owned.msi")
    assert sorted(closed) == acquired and len(closed) == len(set(closed))


def test_arbitrary_property_name_refuses_before_native_query(monkeypatch):
    acquired, closed, queries, _cursors, _modes = _api(monkeypatch)
    with pytest.raises(ValueError, match="Unsupported"):
        reader._property(reader._kernel(), 123, "name' OR 1=1")
    assert acquired == closed == queries == []
