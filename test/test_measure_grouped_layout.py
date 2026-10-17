"""The layout probe measures the actual view/model and checks complete retained rows."""

from __future__ import annotations

import pytest

from je_file_tree.gui import i18n
from tools.measure_grouped_layout import measure


@pytest.mark.parametrize("operation,headers,data", [
    ("noop", 0, 0), ("headers", 1, 0), ("unit", 0, 3),
    ("labels", 0, 3), ("keeper", 0, 2), ("language", 1, 3),
])
def test_probe_dispatches_native_notifications_and_retains_view_state(qapp, operation, headers, data):
    original = i18n.current_language()
    result = measure(qapp, operation, 3, 7)
    assert result["verified"] and all(result["verification"].values())
    assert result["notifications"] == {"headers": headers, "data": data, "resets": 0}
    assert result["members"] == 21 and result["model_class"] == "_CountedModel"
    assert result["platform"] == qapp.platformName() and result["instrumented"]
    assert [entry["number"] for entry in result["event_passes"]] == [1, 2, 3]
    assert i18n.current_language() == original
    if headers:
        assert result["headers"][0] == "名稱"
    if operation == "unit":
        assert result["sample_size"] == "0.0 MB"


def test_probe_counts_deferred_queries_on_the_actual_view_model(qapp, monkeypatch):
    from PySide6.QtCore import QTimer

    from tools import measure_grouped_layout as probe

    apply = probe._apply
    queried = []
    geometry = probe._geometry
    observed_geometry = []

    def capture_geometry(view):
        result = geometry(view)
        observed_geometry.append(result)
        return result

    def delayed_query(model, operation, captured):
        apply(model, operation, captured)
        assert captured.view.model() is model

        def query():
            queried.append(captured.view.model().index(0, 0))

        QTimer.singleShot(0, query)

    monkeypatch.setattr(probe, "_apply", delayed_query)
    monkeypatch.setattr(probe, "_geometry", capture_geometry)
    headers = measure(qapp, "headers", 2, 20)
    assert headers["handler_calls"] == {"index": 0, "flags": 0}
    assert headers["event_passes"][0]["cumulative_calls"]["index"] >= 1 and len(queried) == 1
    assert [headers["geometry_before"], headers["geometry_after"]] == observed_geometry


def test_probe_records_native_header_height_changes_without_clamping_the_view(qapp, monkeypatch):
    from tools import measure_grouped_layout as probe

    apply = probe._apply

    def grow_header(model, operation, captured):
        captured.view.header().setMinimumHeight(captured.view.header().height() + 9)
        apply(model, operation, captured)

    monkeypatch.setattr(probe, "_apply", grow_header)
    result = measure(qapp, "headers", 2, 9)
    before, after = result["geometry_before"], result["geometry_after"]
    assert after["header"][3] >= before["header"][3] + 9
    assert after["viewport"][1] > before["viewport"][1]
    assert after["viewport"][3] < before["viewport"][3]
    assert result["verified"] and result["notifications"] == {"headers": 1, "data": 0, "resets": 0}


def test_uncounted_probe_uses_ordinary_model_and_preserves_single_group_selection(qapp):
    result = measure(qapp, "headers", 1, 9, count_calls=False)
    assert result["verified"] and result["model_class"] == "GroupedListModel"
    assert result["handler_calls"] is None and not result["instrumented"]
    assert all(entry["cumulative_calls"] is None for entry in result["event_passes"])


@pytest.mark.parametrize("groups,members", [(0, 1), (1001, 1), (1, 0), (1000, 1001), (True, 1)])
def test_probe_refuses_unbounded_or_invalid_shapes_before_constructing_a_view(qapp, groups, members):
    with pytest.raises(ValueError, match="Require"):
        measure(qapp, "headers", groups, members)


def test_probe_refuses_unknown_operation(qapp):
    with pytest.raises(ValueError, match="Unknown"):
        measure(qapp, "unexpected", 1, 1)


def test_probe_failure_detaches_its_view_and_restores_the_language(qapp, monkeypatch):
    from tools import measure_grouped_layout as probe

    original_language = i18n.current_language()
    prepared = probe._prepare
    captures = []

    def capture(*args):
        result = prepared(*args)
        captures.append(result)
        return result

    def refuse(*_args):
        i18n.set_language("ko")
        raise RuntimeError("owned probe update failure")

    monkeypatch.setattr(probe, "_prepare", capture)
    monkeypatch.setattr(probe, "_apply", refuse)
    with pytest.raises(RuntimeError, match="owned probe"):
        measure(qapp, "language", 1, 2)
    assert captures[0].view.model() is None and not captures[0].view.isVisible()
    assert i18n.current_language() == original_language
