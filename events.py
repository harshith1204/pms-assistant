import asyncio
from datetime import datetime
from typing import Callable, Any, Awaitable, Dict


class EventEmitter:
    def __init__(self):
        self._subs = []  # list of async callbacks: Callable[[dict], Awaitable[None]]
        self._seq = 0
        self._lock = asyncio.Lock()

    def subscribe(self, coro: Callable[[dict], Awaitable[None]]):
        """Subscribe an async callback to receive events.
        The callback should accept a single dict argument.
        """
        self._subs.append(coro)

    async def emit(self, event: Dict[str, Any]):
        """Emit an event to all subscribers. Adds timestamp and sequence automatically.
        Does not raise subscriber exceptions.
        """
        async with self._lock:
            self._seq += 1
            seq = self._seq
        event.setdefault("sequence", seq)
        event.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
        event.setdefault("type", "agent_log")
        # Fan out concurrently; do not await each to avoid head-of-line blocking
        for sub in list(self._subs):
            try:
                result = sub(event)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception:
                # Never let subscriber errors bubble up
                pass

    def emit_sync(self, event: Dict[str, Any]):
        """Schedule an emit from sync contexts.
        If no running loop is available, falls back to asyncio.run.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.emit(event))
                return
        except Exception:
            pass
        asyncio.run(self.emit(event))


# Global emitter instance
emitter = EventEmitter()
