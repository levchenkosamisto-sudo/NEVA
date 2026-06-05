import sys
import json
import os
import logging

log_path = os.path.expanduser("~/Library/Logs/NEVA/mcp_server.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)
logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_validator import validate
from mcp_executor import run


def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    logger.info("NEVA MCP Server started")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue

        rid = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})
        logger.info(f"{method} id={rid}")

        if method == "initialize":
            send({
                "jsonrpc": "2.0", "id": rid,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "neva_executor", "version": "1.0"},
                    "capabilities": {"tools": {}}
                }
            })
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            send({
                "jsonrpc": "2.0", "id": rid,
                "result": {"tools": [{
                    "name": "neva_execute",
                    "description": "NEVA MCP Executor. Actions: git_status, file_tree, file_read, system_info, run_tests, diagnostics, ollama_list",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "params": {"type": "object", "additionalProperties": True}
                        },
                        "required": ["action"]
                    }
                }]}
            })
        elif method == "tools/call":
            args = params.get("arguments", {})
            result = run(validate(json.dumps(args)))
            logger.info(f"execute {args.get('action')} -> {result.get('status')}")
            send({
                "jsonrpc": "2.0", "id": rid,
                "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}
            })
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": rid, "result": {}})
        else:
            send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Method not found: {method}"}})


if __name__ == "__main__":
    main()
