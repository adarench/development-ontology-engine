"""Fan-out across registered notifiers."""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable, List

from core.engine.notifiers.base import NotificationContext, Notifier

log = logging.getLogger(__name__)


class NotificationDispatcher:
    """Holds the active set of notifiers and fans out one notification across
    all of them concurrently. Per-channel errors are logged, never raised."""

    def __init__(self, notifiers: Iterable[Notifier]) -> None:
        self._notifiers: List[Notifier] = list(notifiers)

    @property
    def channels(self) -> List[str]:
        return [n.name for n in self._notifiers]

    async def notify(self, ctx: NotificationContext) -> None:
        coros = []
        for n in self._notifiers:
            if not n.supports(ctx):
                continue
            coros.append(self._safe_notify(n, ctx))
        if coros:
            await asyncio.gather(*coros)

    async def _safe_notify(self, n: Notifier, ctx: NotificationContext) -> None:
        try:
            await n.notify(ctx)
        except Exception:  # noqa: BLE001 — channels must never break the dispatcher
            log.exception(
                "notifier %s failed for queue_item=%s payload_type=%s",
                n.name,
                ctx.queue_item_id,
                ctx.payload_type,
            )
