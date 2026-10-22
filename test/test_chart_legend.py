"""Legend entries wrap as complete labels without invisible font-fallback triggers."""

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QFont, QTextDocument

from je_file_tree.gui.chart_legend import ChartLegend


@pytest.mark.parametrize("text", ["Code and data (5.0 MB)", "程式碼與資料 (5.0 MB)",
                                  "コードとデータ (5.0 MB)", "코드와 데이터 (5.0 MB)", '<cache> & "data"'])
def test_legend_keeps_literal_complete_entries_and_wraps_between_them(qapp, text):
    legend = ChartLegend()
    legend.set_items([("#06989a", text), ("#3465a4", text), ("#cc0000", text)])
    labels = legend.labels()
    assert [label.accessibleName() for label in labels] == [text] * 3
    assert all(not label.wordWrap() and "\u2060" not in label.text() for label in labels)
    document = QTextDocument()
    document.setHtml(labels[0].text())
    assert document.toPlainText() == "■ " + text
    width = max(label.sizeHint().width() for label in labels)
    height = legend.heightForWidth(width)
    legend.resize(width, height)
    legend.layout().setGeometry(QRect(0, 0, width, height))
    rectangles = [label.geometry() for label in labels]
    assert len({rect.y() for rect in rectangles}) == 3
    assert all(legend.rect().contains(rect) for rect in rectangles)
    assert all(rect.width() == label.sizeHint().width() for rect, label in zip(rectangles, labels, strict=True))
    wide = sum(label.sizeHint().width() for label in labels) + 100
    assert legend.heightForWidth(wide) < height
    legend.resize(wide, legend.heightForWidth(wide))
    legend.layout().setGeometry(legend.rect())
    assert len({label.y() for label in labels}) == 1
    legend.deleteLater()


def test_legend_reuses_unchanged_entries_and_releases_removed_rows(qapp):
    legend = ChartLegend()
    items = [("#06989a", "Code and data"), ("#cc0000", "Images")]
    legend.set_items(items)
    labels = legend.labels()
    legend.set_items(items)
    assert legend.labels() == labels
    legend.set_items([("#3465a4", "Documents")])
    assert all(label.isHidden() for label in labels)
    assert len(legend.labels()) == legend.layout().count() == 1
    assert legend.labels()[0].accessibleName() == "Documents"
    legend.set_items([])
    assert legend.heightForWidth(100) == 0
    assert legend.layout().count() == 0
    legend.deleteLater()


def test_legend_remeasures_after_font_changes(qapp):
    legend = ChartLegend()
    legend.set_items([("#06989a", "Code and data"), ("#cc0000", "Images")])
    width = sum(label.sizeHint().width() for label in legend.labels()) + 20
    before = legend.heightForWidth(width)
    larger = QFont(legend.font())
    larger.setPointSizeF(24)
    legend.setFont(larger)
    assert legend.heightForWidth(width) > before
    legend.deleteLater()
