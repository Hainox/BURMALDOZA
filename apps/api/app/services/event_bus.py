from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from burmaldoza_contracts.events import EventEnvelope


class EventBus:
    """In-process notification bus; PostgreSQL remains the durable source of truth."""

    def __init__(self) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue[EventEnvelope]]] = defaultdict(set)

    async def publish(self, event: EventEnvelope) -> None:
        for queue in tuple(self._subscribers.get(event.room_id, ())):
            await queue.put(event)

    @asynccontextmanager
    async def subscribe(self, room_id: UUID) -> AsyncIterator[asyncio.Queue[EventEnvelope]]:
        queue: asyncio.Queue[EventEnvelope] = asyncio.Queue()
        self._subscribers[room_id].add(queue)
        try:
            yield queue
        finally:
            subscribers = self._subscribers.get(room_id)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    self._subscribers.pop(room_id, None)
