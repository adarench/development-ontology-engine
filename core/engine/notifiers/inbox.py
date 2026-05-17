"""Inbox notifier — the always-on V1 channel.

The "inbox" is the `queue_items` table itself. Once M6 lands, writing the
queue row IS the inbox notification — a human polls the API to see open items.

This notifier exists so the notifier abstraction stays honest: every channel
implements the same contract, and adding email/Slack later is symmetric with
adding inbox today. The `notify` method here is intentionally a no-op log line.
"""
from __future__ import annotations

import logging

from core.engine.notifiers.base import NotificationContext

log = logging.getLogger(__name__)


class InboxNotifier:
    name = "inbox"

    def supports(self, ctx: NotificationContext) -> bool:
        return True

    async def notify(self, ctx: NotificationContext) -> None:
        log.info(
            "inbox: queue_item=%s run=%s payload_type=%s roles=%s",
            ctx.queue_item_id,
            ctx.run_id,
            ctx.payload_type,
            ctx.authorized_roles,
        )
