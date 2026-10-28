"""Send local Qt keyboard events only to the window's actual focus widget."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView, QApplication, QScrollArea, QWidget


PIXEL_RATIO_TOLERANCE = 0.01


def prepare_hidden(widget: QWidget) -> None:
    """Place a hidden native widget on a screen with the requested actual scale."""
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    expected = float(os.environ.get('QT_SCALE_FACTOR', '1'))
    screen = next((screen for screen in QApplication.screens()
                   if abs(screen.devicePixelRatio() - expected) < PIXEL_RATIO_TOLERANCE), None)
    if screen is None:
        raise RuntimeError('No native screen provides the requested pixel ratio')
    widget.setScreen(screen)
    widget.move(screen.availableGeometry().topLeft())


def focused(window: QWidget) -> QWidget:
    """Return a visible focused control, refusing absent or clipped keyboard targets."""
    widget = window.focusWidget()
    if widget is None or not widget.isVisibleTo(window):
        raise RuntimeError(f'{window.objectName() or type(window).__name__}: no visible keyboard focus')
    ancestor = widget.parentWidget()
    while ancestor is not None and ancestor is not window:
        if isinstance(ancestor, QScrollArea):
            viewport = ancestor.viewport()
            bounds = widget.rect().translated(widget.mapTo(viewport, widget.rect().topLeft()))
            if not viewport.rect().intersects(bounds):
                raise RuntimeError(f'Focused {type(widget).__name__} is outside its scroll viewport')
        ancestor = ancestor.parentWidget()
    return widget


def key(window: QWidget, value: Qt.Key, modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
    """Send one key to existing focus, without choosing or activating a native window."""
    QTest.keyClick(focused(window), value, modifier)
    QApplication.processEvents()


def tab_to(window: QWidget, target: QWidget, *, backwards: bool = False) -> None:
    """Reach a control using the real Tab chain, failing on a cycle or inaccessible target."""
    visited = set()
    for _ in range(100):
        current = focused(window)
        if current is target:
            return
        index = current.currentIndex() if isinstance(current, QAbstractItemView) else None
        position = (index.row(), index.column()) if index is not None else None
        state = (id(current), position)
        if state in visited:
            raise RuntimeError(f'Tab cycle before {target.accessibleName() or type(target).__name__}; '
                               f'focused={type(current).__name__}, cell={position}, visited={len(visited)}')
        visited.add(state)
        key(window, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier if backwards
            else Qt.KeyboardModifier.NoModifier)
    raise RuntimeError('Tab traversal exceeded its bounded control count')


def replace_text(window: QWidget, target: QWidget, text: str) -> None:
    """Reach an input and replace it through Select All and text key events."""
    tab_to(window, target)
    key(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    key(window, Qt.Key.Key_Backspace)
    QTest.keyClicks(focused(window), text)
    QApplication.processEvents()


def press(window: QWidget, target: QWidget) -> None:
    """Tab to a button and activate the focused control with Space."""
    tab_to(window, target)
    key(window, Qt.Key.Key_Space)


def select_all(window: QWidget, target: QWidget, expected: str) -> None:
    """Prove complete input text is keyboard-selectable without touching the clipboard."""
    tab_to(window, target)
    key(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    if target.selectedText() != expected:
        raise RuntimeError('Keyboard Select All did not expose the complete literal text')


def verify_scale(widget: QWidget) -> float:
    """Reject an environment scale that did not reach the native widget."""
    expected = float(os.environ.get('QT_SCALE_FACTOR', '1'))
    actual = widget.devicePixelRatioF()
    if abs(expected - actual) > PIXEL_RATIO_TOLERANCE:
        raise RuntimeError(f'Expected native pixel ratio {expected}, observed {actual}')
    return actual
