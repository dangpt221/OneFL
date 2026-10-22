"""Per-event-loop admission shared by service and Agent entry points."""
import asyncio
from functools import wraps
from weakref import WeakKeyDictionary

_loops = WeakKeyDictionary()


def bounded_resource(name, capacity):
    def decorate(function):
        @wraps(function)
        async def limited(*args, **kwargs):
            limits = _loops.setdefault(asyncio.get_running_loop(), {})
            semaphore = limits.setdefault(name, asyncio.Semaphore(max(1, int(capacity()))))
            async with semaphore:
                return await function(*args, **kwargs)
        return limited
    return decorate
