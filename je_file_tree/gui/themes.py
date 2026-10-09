"""Application-wide native/system or explicit light/dark palettes with persisted menu choices."""

from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QPalette
from PySide6.QtWidgets import QApplication, QMenu

from je_file_tree.gui.i18n import tr

THEMES = ('system', 'light', 'dark')
_LIGHT = {
    'Window': '#f3f4f6', 'Base': '#ffffff', 'AlternateBase': '#f0f3f8',
    'Text': '#17202a', 'WindowText': '#17202a', 'Button': '#e8ecf2', 'ButtonText': '#17202a',
    'Highlight': '#245ba5', 'HighlightedText': '#ffffff', 'Mid': '#8794a4',
    'Dark': '#a4afbd', 'Light': '#ffffff', 'Midlight': '#e0e5ec', 'Shadow': '#667482',
    'ToolTipBase': '#fffbe5', 'ToolTipText': '#17202a', 'Link': '#205aa0', 'LinkVisited': '#7747a6',
    'PlaceholderText': '#657283', 'BrightText': '#a51d2d',
}
_DARK = {
    'Window': '#292d33', 'Base': '#20242a', 'AlternateBase': '#30363e',
    'Text': '#e8edf3', 'WindowText': '#e8edf3', 'Button': '#3a424c', 'ButtonText': '#e8edf3',
    'Highlight': '#2d6acc', 'HighlightedText': '#ffffff', 'Mid': '#74808f',
    'Dark': '#15191f', 'Light': '#586577', 'Midlight': '#3e4856', 'Shadow': '#0f141a',
    'ToolTipBase': '#e8edf3', 'ToolTipText': '#17202a', 'Link': '#86baff', 'LinkVisited': '#cfafff',
    'PlaceholderText': '#a0acbc', 'BrightText': '#ff97a7',
}


def theme_palette(theme: str) -> QPalette:
    """Build an explicit palette; an empty system palette restores Qt's native platform defaults."""
    palette = QPalette()
    if theme not in ('light', 'dark'):
        return palette
    for role, colour in (_LIGHT if theme == 'light' else _DARK).items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(colour))
    disabled = QColor('#657283' if theme == 'light' else '#a0acbc')
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return palette


class ThemeController(QObject):
    """Own the native style once, switching explicit palettes without changing scan data."""

    changed = Signal(str)

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self.app = app
        self.native_style = app.style().objectName()
        self.choice = 'system'

    def apply(self, theme: str) -> None:
        """Apply one validated choice; System resets the palette's resolve mask to native defaults."""
        theme = theme if theme in THEMES else 'system'
        self.app.setStyle(self.native_style if theme == 'system' else 'Fusion')
        self.app.setPalette(theme_palette(theme))
        self.choice = theme
        self.changed.emit(theme)


def theme_controller() -> ThemeController:
    """Return the single controller attached to this QApplication, creating it before any override."""
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError('a QApplication is required')
    controller = getattr(app, '_filetree_theme_controller', None)
    if controller is None:
        controller = ThemeController(app)
        app._filetree_theme_controller = controller
    return controller


class ThemeMenu(QMenu):
    """A translated exclusive View → Theme submenu, with an independent saved setting."""

    def __init__(self, parent: QMenu, settings: QSettings) -> None:
        super().__init__(parent)
        parent.addMenu(self)
        self.settings = settings
        self.controller = theme_controller()
        group = QActionGroup(self)
        self.actions_by_theme: dict[str, QAction] = {}
        for theme in THEMES:
            action = self.addAction('')
            action.setCheckable(True)
            group.addAction(action)
            action.triggered.connect(lambda _checked=False, choice=theme: self._choose(choice))
            self.actions_by_theme[theme] = action
        self.controller.changed.connect(self._mark)
        self._mark(self.controller.choice)
        self.retranslate()

    def retranslate(self) -> None:
        """Refresh the submenu labels in the current language without changing the choice."""
        self.setTitle(tr('menu_theme'))
        for theme, action in self.actions_by_theme.items():
            action.setText(tr(f'theme_{theme}'))

    def _choose(self, theme: str) -> None:
        self.settings.setValue('theme', theme)
        self.controller.apply(theme)

    def _mark(self, theme: str) -> None:
        self.actions_by_theme[theme].setChecked(True)
