"""Notifier abstraction + dispatcher fan-out + registry env wiring."""
import asyncio

import pytest

from core.engine.notifiers import (
    InboxNotifier,
    NotificationContext,
    NotificationDispatcher,
    available_notifiers,
    build_dispatcher,
    register_notifier,
)


def _ctx(payload_type: str = "inline_approval") -> NotificationContext:
    return NotificationContext(
        queue_item_id=1,
        run_id=2,
        payload_type=payload_type,
        payload={"q": "go?"},
        authorized_roles=["approver"],
    )


class _Recorder:
    def __init__(self, name: str, supports_filter=lambda ctx: True):
        self.name = name
        self.calls: list = []
        self._supports = supports_filter

    def supports(self, ctx):
        return self._supports(ctx)

    async def notify(self, ctx):
        self.calls.append(ctx)


class _Broken:
    name = "broken"

    def supports(self, ctx):
        return True

    async def notify(self, ctx):
        raise RuntimeError("boom")


class TestInboxNotifier:
    def test_implements_protocol(self):
        n = InboxNotifier()
        assert n.name == "inbox"
        assert n.supports(_ctx()) is True

    def test_notify_runs_without_raising(self):
        asyncio.run(InboxNotifier().notify(_ctx()))


class TestDispatcher:
    def test_fan_out_calls_every_supporting_channel(self):
        a = _Recorder("a")
        b = _Recorder("b")
        d = NotificationDispatcher([a, b])
        ctx = _ctx()
        asyncio.run(d.notify(ctx))
        assert a.calls == [ctx]
        assert b.calls == [ctx]

    def test_unsupported_channel_skipped(self):
        a = _Recorder("a", supports_filter=lambda ctx: False)
        b = _Recorder("b")
        d = NotificationDispatcher([a, b])
        asyncio.run(d.notify(_ctx()))
        assert a.calls == []
        assert len(b.calls) == 1

    def test_failure_in_one_channel_does_not_break_others(self):
        a = _Recorder("a")
        broken = _Broken()
        b = _Recorder("b")
        d = NotificationDispatcher([a, broken, b])
        asyncio.run(d.notify(_ctx()))
        assert len(a.calls) == 1
        assert len(b.calls) == 1

    def test_channels_property(self):
        d = NotificationDispatcher([_Recorder("a"), _Recorder("b")])
        assert d.channels == ["a", "b"]


class TestRegistry:
    def test_inbox_is_always_available(self):
        assert "inbox" in available_notifiers()

    def test_build_default_includes_inbox(self):
        d = build_dispatcher(channels_env="")
        assert d.channels == ["inbox"]

    def test_unknown_channel_warned_not_raised(self):
        d = build_dispatcher(channels_env="inbox,ghost")
        assert d.channels == ["inbox"]  # ghost dropped silently

    def test_inbox_always_included_even_if_omitted(self):
        d = build_dispatcher(channels_env="ghost")
        assert "inbox" in d.channels

    def test_register_then_select(self):
        register_notifier(_Recorder("test_channel_xyz"))
        d = build_dispatcher(channels_env="inbox,test_channel_xyz")
        assert "test_channel_xyz" in d.channels

    def test_re_register_replaces_previous(self):
        r1 = _Recorder("dup_name")
        r2 = _Recorder("dup_name")
        register_notifier(r1)
        register_notifier(r2)
        d = build_dispatcher(channels_env="inbox,dup_name")
        # the active dispatcher should hold r2, not r1
        asyncio.run(d.notify(_ctx()))
        assert len(r1.calls) == 0
        assert len(r2.calls) == 1


class TestNotificationContext:
    def test_frozen(self):
        ctx = _ctx()
        with pytest.raises(Exception):
            ctx.queue_item_id = 99  # type: ignore[misc]
