from __future__ import annotations

from dataclasses import dataclass
from queue import Full, Queue
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkItem:
    kind: str
    payload: Any = None


class BoundedWorkQueue:
    def __init__(self, max_size: int = 2048):
        self._queue: Queue[WorkItem] = Queue(maxsize=max(100, int(max_size)))

    def put(self, item: WorkItem) -> bool:
        try:
            self._queue.put_nowait(item)
            return True
        except Full:
            return False

    def get(self, timeout: float = 0.25) -> WorkItem:
        return self._queue.get(timeout=timeout)

    def get_nowait(self) -> WorkItem:
        return self._queue.get_nowait()

    @property
    def size(self) -> int:
        return self._queue.qsize()
