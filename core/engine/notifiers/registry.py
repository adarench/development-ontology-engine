"""Channel registry + env-driven dispatcher builder.

A channel registers itself by name. The active dispatcher is built from the
`NOTIFICATION_CHANNELS` env var (comma-separated).

Adding a new channel (e.g. email in Phase 2):

  # core/engine/notifiers/email.py
  from .registry import register_notifier
  class EmailNotifier: ...
  register_notifier(EmailNotifier())

Then set `NOTIFICATION_CHANNELS=inbox,email` and the dispatcher picks it up.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List

from core.engine.notifiers.base import Notifier
from core.engine.notifiers.dispatcher import NotificationDispatcher
from core.engine.notifiers.inbox import InboxNotifier

log = logging.getLogger(__name__)


_NOTIFIERS: Dict[str, Notifier] = {}


def register_notifier(notifier: Notifier) -> None:
    """Register a channel. Idempotent on name — re-registering replaces the
    previous instance (handy for tests)."""
    _NOTIFIERS[notifier.name] = notifier


def available_notifiers() -> List[str]:
    return sorted(_NOTIFIERS.keys())


def build_dispatcher(channels_env: str | None = None) -> NotificationDispatcher:
    """Read `NOTIFICATION_CHANNELS` from env (or the explicit arg for tests)
    and build the dispatcher with the selected channels. `inbox` is always
    included even if missing from the env — losing it would silently strip
    the V1 guarantee that decisions land somewhere a human can find."""
    raw = channels_env if channels_env is not None else os.environ.get(
        "NOTIFICATION_CHANNELS", "inbox"
    )
    requested = [c.strip() for c in raw.split(",") if c.strip()]
    if "inbox" not in requested:
        requested.insert(0, "inbox")

    active: List[Notifier] = []
    for name in requested:
        n = _NOTIFIERS.get(name)
        if n is None:
            log.warning("notification channel %r requested but not registered", name)
            continue
        active.append(n)
    return NotificationDispatcher(active)


# Always-on default channel.
register_notifier(InboxNotifier())
