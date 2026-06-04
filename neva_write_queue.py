import asyncio
import inspect
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

_write_lock = asyncio.Lock()
_write_counter = 0

async def write_to_graph(operation, *args, **kwargs):
    global _write_counter
    async with _write_lock:
        _write_counter += 1
        op_id = _write_counter
        result = operation(*args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result

def get_write_counter():
    return _write_counter

def reset_write_counter():
    global _write_counter
    _write_counter = 0
