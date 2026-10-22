"""Application-wide Fluent light/dark themes (System follows the platform) with a persisted menu choice."""

from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QPalette, QStyleHints
from PySide6.QtWidgets import QApplication, QMenu

from je_file_tree.gui.fluent_style import FluentStyle, style_sheet, tokens_for
from je_file_tree.gui.i18n import tr

THEMES = ('system', 'light', 'dark')
NATIVE = 'native'  # the platform's own style and palette, used for System under high contrast


def theme_palette(theme: str, accent: QColor | str | None = None) -> QPalette:
    """Build the palette for ``light``/``dark`` from the Fluent tokens; anything else is empty (native)."""
    palette = QPalette()
    if theme not in ('light', 'dark'):
        return palette
    t = tokens_for(theme, accent)
    roles = {
        'Window': t.window, 'WindowText': t.text, 'Base': t.card, 'AlternateBase': t.subtle,
        'Text': t.text, 'Button': t.control, 'ButtonText': t.text, 'BrightText': t.on_accent,
        'Highlight': t.accent, 'HighlightedText': t.on_accent, 'Accent': t.accent,
        'Light': t.card, 'Midlight': t.stroke, 'Mid': t.stroke_strong, 'Dark': t.stroke_strong,
        'Shadow': '#000000', 'ToolTipBase': t.card, 'ToolTipText': t.text,
        'Link': t.link, 'LinkVisited': t.link, 'PlaceholderText': t.text_secondary,
    }
    for role, colour in roles.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(colour))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(t.text_disabled))
    return palette


def _high_contrast(hints: QStyleHints) -> bool:
    """Whether the platform asks for high contrast (Qt 6.10+; older Qt cannot tell and answers no)."""
    accessibility = getattr(hints, 'accessibility', None)
    if accessibility is None:
        return False
    return accessibility().contrastPreference() == Qt.ContrastPreference.HighContrast


class ThemeController(QObject):
    """Apply one Fluent palette and style sheet application-wide, without changing scan data.

    System follows the platform's light/dark setting (and re-applies when it changes) unless the
    platform asks for high contrast, which keeps the native style and palette. Every theme uses
    the platform accent captured before the first override.
    """

    changed = Signal(str)

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self.app = app
        self.native_style = app.style().objectName()
        self.accent = QColor(app.palette().color(QPalette.ColorRole.Accent))
        self.choice = 'system'
        self.resolved = NATIVE
        self.style: FluentStyle | None = None  # the applied style; Qt wraps it while a style sheet is set
        self._applying = False
        # Style sheets otherwise stop fonts set on a window (language fonts) reaching its children.
        app.setAttribute(Qt.ApplicationAttribute.AA_UseStyleSheetPropagationInWidgetStyles, True)
        app.styleHints().colorSchemeChanged.connect(self._platform_changed)

    def resolve(self, theme: str) -> str:
        """The scheme a choice shows now: ``light``, ``dark`` or ``native``."""
        if theme in ('light', 'dark'):
            return theme
        hints = self.app.styleHints()
        if _high_contrast(hints):
            return NATIVE
        return 'dark' if hints.colorScheme() == Qt.ColorScheme.Dark else 'light'

    def apply(self, theme: str) -> None:
        """Apply one validated choice; repeated calls with the same platform state change nothing visible."""
        theme = theme if theme in THEMES else 'system'
        self._applying = True
        try:
            self._follow_platform_scheme(theme)
            resolved = self.resolve(theme)
            if resolved == self.resolved and (resolved == NATIVE or self.style is not None):
                # Re-setting an identical sheet repolishes every existing widget; each new window
                # applies the saved theme, so skip the work when nothing would change.
                pass
            elif resolved == NATIVE:
                self.app.setStyleSheet('')
                self.app.setStyle(self.native_style)
                self.app.setPalette(QPalette())
                self.style = None
            else:
                tokens = tokens_for(resolved, self.accent)
                self.style = FluentStyle(tokens)
                self.app.setStyle(self.style)
                self.app.setPalette(theme_palette(resolved, self.accent))
                self.app.setStyleSheet(style_sheet(tokens))
        finally:
            self._applying = False
        self.choice, self.resolved = theme, resolved
        self.changed.emit(theme)

    def _follow_platform_scheme(self, theme: str) -> None:
        """Ask the platform for a matching title bar on explicit themes (Qt 6.8+); System follows it."""
        set_scheme = getattr(self.app.styleHints(), 'setColorScheme', None)
        if set_scheme is None:
            return
        scheme = {'light': Qt.ColorScheme.Light, 'dark': Qt.ColorScheme.Dark}.get(theme, Qt.ColorScheme.Unknown)
        set_scheme(scheme)

    def _platform_changed(self, _scheme: Qt.ColorScheme) -> None:
        if self.choice == 'system' and not self._applying:
            self.apply('system')


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
