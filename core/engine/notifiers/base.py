"""Notifier contract.

A `Notifier` is a single delivery channel — inbox, email, Slack, etc.
The dispatcher fans out one notification across every registered notifier.

`NotificationContext` is the minimal payload notifiers receive. It's a
plain dataclass rather than the `QueueItem` ORM model so the notifier layer
stays decoupled from the DB layer (and so M6's queue work doesn't force
notifier refactors).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class NotificationContext:
    """Everything a channel needs to deliver one notification.

    Fields are deliberately minimal. Channels that need more (HTML body, links,
    attachments) should construct them from this context at send time.
    """

    queue_item_id: int
    run_id: int
    payload_type: str
    payload: Dict[str, Any]
    authorized_roles: List[str]
    # Optional recipient. Inbox doesn't need one; email/Slack do.
    recipient_email: Optional[str] = None
    recipient_slack_id: Optional[str] = None


@runtime_checkable
class Notifier(Protocol):
    """Single delivery channel.

    Implementations must be safe to call concurrently and must not raise on
    transient failures — return cleanly and let the dispatcher log + move on.
    The queue row is the source of truth; a missed email never blocks a human
    from finding the work via the inbox.
    """

    name: str

    def supports(self, ctx: NotificationContext) -> bool:
        """Whether this channel should fire for the given context.

        Channels can opt out per payload_type (e.g. email-only for urgent
        approvals) or per recipient (no slack_id → no slack notification).
        """
        ...

    async def notify(self, ctx: NotificationContext) -> None:
        """Best-effort dispatch. Must swallow its own transient errors and
        return cleanly. The dispatcher logs unexpected exceptions but does not
        retry."""
        ...
