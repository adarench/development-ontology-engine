"""Notification channels.

V1 ships **inbox-only** — queue items live in Postgres and a human polls them.
The abstraction here exists so email / Slack / push channels are a single new
file each, not a refactor.

Channels are selected via the `NOTIFICATION_CHANNELS` env var (comma-separated).
Unknown channel names are ignored with a warning.
"""

from core.engine.notifiers.base import (
    NotificationContext,
    Notifier,
)
from core.engine.notifiers.dispatcher import NotificationDispatcher
from core.engine.notifiers.inbox import InboxNotifier
from core.engine.notifiers.registry import (
    available_notifiers,
    build_dispatcher,
    register_notifier,
)

__all__ = [
    "NotificationContext",
    "Notifier",
    "NotificationDispatcher",
    "InboxNotifier",
    "available_notifiers",
    "build_dispatcher",
    "register_notifier",
]
