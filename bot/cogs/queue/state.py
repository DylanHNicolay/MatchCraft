import asyncio
from dataclasses import dataclass, field
from typing import Any

PHASE_OPEN = "open"
PHASE_CLOSING = "closing"
PHASE_STARTED = "started"


@dataclass
class QueueState:
    name: str
    max_players: int
    players: list[Any] = field(default_factory=list)
    msg_id: int | None = None
    vc: Any | None = None
    start: bool = False
    phase: str = PHASE_OPEN
    revision: int = 0
    draft: dict[str, Any] | None = None

    def bump_revision(self):
        self.revision += 1


class QueueStore:
    def __init__(self):
        self._queues: dict[int, QueueState] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    @property
    def global_lock(self) -> asyncio.Lock:
        return self._global_lock

    def has_queue(self, channel_id: int) -> bool:
        return channel_id in self._queues

    def get_queue(self, channel_id: int) -> QueueState | None:
        return self._queues.get(channel_id)

    def get_lock(self, channel_id: int) -> asyncio.Lock:
        if channel_id not in self._locks:
            self._locks[channel_id] = asyncio.Lock()
        return self._locks[channel_id]

    async def create_queue(self, channel_id: int, name: str, max_players: int) -> QueueState | None:
        async with self._global_lock:
            if channel_id in self._queues:
                return None

            queue = QueueState(name=name, max_players=max_players)
            self._queues[channel_id] = queue
            self._locks[channel_id] = asyncio.Lock()
            return queue

    def remove_queue(self, channel_id: int):
        self._queues.pop(channel_id, None)
        self._locks.pop(channel_id, None)
