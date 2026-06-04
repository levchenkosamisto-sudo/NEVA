import json
import time
import os

LOG_FILE = os.path.expanduser(
    "~/Documents/NEVA/tools/mcp_executor/graph/execution.log"
)

MAX_BUFFER = 50
_buffer = []


def _flush():
    global _buffer

    if not _buffer:
        return

    try:
        with open(LOG_FILE, "a") as f:
            for entry in _buffer:
                f.write(json.dumps(entry) + "\n")
    except Exception:
        # fail-safe: не ломаем executor
        pass

    _buffer = []


def log_execution(action: str, payload: dict, result: dict):
    entry = {
        "timestamp": time.time(),
        "action": action,
        "payload": payload,
        "result": result
    }

    _buffer.append(entry)

    if len(_buffer) >= MAX_BUFFER:
        _flush()

    return {
        "status": "buffered",
        "buffer_size": len(_buffer)
    }


def force_flush():
    _flush()
    return {"status": "flushed"}
