import asyncio

from app import live


def test_publish_with_no_subscribers_is_noop():
    live.publish("call-none", "abc")


def test_subscribe_receives_published_audio():
    async def scenario():
        queue = live.subscribe("call-1")
        live.publish("call-1", "abc")
        chunk = await asyncio.wait_for(queue.get(), timeout=1)
        assert chunk == "abc"
        live.unsubscribe("call-1", queue)

    asyncio.run(scenario())


def test_unsubscribe_stops_delivery():
    async def scenario():
        queue = live.subscribe("call-2")
        live.unsubscribe("call-2", queue)
        live.publish("call-2", "abc")
        assert queue.empty()

    asyncio.run(scenario())


def test_publish_fans_out_to_multiple_subscribers():
    async def scenario():
        q1 = live.subscribe("call-3")
        q2 = live.subscribe("call-3")
        live.publish("call-3", "abc")
        assert await asyncio.wait_for(q1.get(), timeout=1) == "abc"
        assert await asyncio.wait_for(q2.get(), timeout=1) == "abc"
        live.unsubscribe("call-3", q1)
        live.unsubscribe("call-3", q2)

    asyncio.run(scenario())
