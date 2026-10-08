"""Reentrant dated-proposal metadata checks with a separate QSettings instance in the calling thread."""

from __future__ import annotations

from dataclasses import dataclass
import time

from PySide6.QtCore import QSettings

from je_file_tree.core.background import MonitorConfig, dump_attempts, load_attempts, load_config
from je_file_tree.core.cleanup_policy import CleanupPolicy, load_policy
from je_file_tree.core.recurring import RecurringProposal, binding_status


@dataclass(frozen=True, slots=True)
class ProposalSettings:
    """Scalar settings location only; no GUI-owned QObject is read from an operation worker."""

    file_name: str
    format: QSettings.Format
    namespace: tuple[QSettings.Scope, str, str] | None
    group: str
    fallbacks: bool

    @classmethod
    def capture(cls, settings: QSettings) -> ProposalSettings:
        """Capture an integration's exact backend/group/fallback contract on its owning GUI thread."""
        namespace = ((settings.scope(), settings.organizationName(), settings.applicationName())
                     if settings.organizationName() else None)
        return cls(settings.fileName(), settings.format(), namespace, settings.group(), settings.fallbacksEnabled())

    def status(self, report: RecurringProposal) -> str | None:
        """Reopen/sync on this thread and fail closed on unavailable, changed or malformed dated bindings."""
        settings = (QSettings(self.file_name, self.format) if self.namespace is None else
                    QSettings(self.format, *self.namespace))
        if settings.fileName() != self.file_name:
            return "unavailable"
        settings.setFallbacksEnabled(self.fallbacks)
        settings.beginGroup(self.group)
        settings.sync()
        if settings.status() != QSettings.Status.NoError:
            return "unavailable"
        try:
            attempts = load_attempts(settings.value("background_attempts", dump_attempts({})))
            policy_text, config_text = settings.value("cleanup_policy", None), settings.value("background_config", None)
            policy = CleanupPolicy() if policy_text is None else load_policy(policy_text)
            config = MonitorConfig() if config_text is None else load_config(config_text)
            return binding_status(report, policy, config, attempts.get(report.context.attempt.key), time.time())
        except (OSError, ValueError):
            return "unavailable"
