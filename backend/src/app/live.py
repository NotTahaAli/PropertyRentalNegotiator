import asyncio

# ponytail: single-process fan-out; one free-tier Render worker, no cross-worker pub/sub.
_subscribers: dict[str, set[asyncio.Queue]] = {}


def subscribe(call_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(call_id, set()).add(queue)
    return queue


def unsubscribe(call_id: str, queue: asyncio.Queue) -> None:
    queues = _subscribers.get(call_id)
    if not queues:
        return
    queues.discard(queue)
    if not queues:
        _subscribers.pop(call_id, None)


def publish(call_id: str, audio_base_64: str) -> None:
    for queue in _subscribers.get(call_id, ()):
        queue.put_nowait(audio_base_64)
