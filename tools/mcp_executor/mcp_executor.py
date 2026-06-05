import os
import subprocess
import time

from graph.execution_logger import log_execution

BASE_DIR = os.path.realpath(os.path.expanduser("~/Documents/NEVA_MCP_BRIDGE"))


def safe_path(path: str):
    if not path:
        return None

    full = os.path.realpath(os.path.join(BASE_DIR, os.path.expanduser(path)))

    if not full.startswith(BASE_DIR + os.sep) and full != BASE_DIR:
        return None

    return full


def run_tests():
    start = time.time()
    try:
        result = subprocess.run(
            ["pytest"],
            capture_output=True,
            text=True,
            timeout=60
        )
        return {
            "status": "ok",
            "output": result.stdout[-2000:],
            "errors": result.stderr[-2000:],
            "time_ms": int((time.time() - start) * 1000)
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "blocked",
            "reason": "TIMEOUT"
        }


def execute(command: dict):
    action = command.get("action")

    if action == "git_status":
        return {"status": "ok", "action": action, "result": "ON_BRANCH_MAIN"}

    if action == "file_tree":
        return {"status": "ok", "action": action, "result": "TREE_STAGE_5"}

    if action == "file_read":
        path = safe_path(command.get("params", {}).get("path", ""))

        if not path:
            return {"status": "blocked", "reason": "PATH_ESCAPE_BLOCKED"}

        return {
            "status": "ok",
            "action": action,
            "file": path,
            "content": "READONLY_CONTENT_STAGE_5"
        }

    if action == "run_playbook":
        name = command.get("params", {}).get("name")

        if name == "diagnostics":
            return {
                "status": "ok",
                "playbook": "diagnostics",
                "result": "STUB_STAGE_5"
            }

        return {"status": "blocked", "reason": "UNKNOWN_PLAYBOOK"}

    if action == "run_tests":
        return run_tests()

    if action == "ollama_list":
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return {"status": "ok", "output": result.stdout}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    if action == "ollama_run":
        return {"status": "blocked", "reason": "REQUIRES_DIRECTOR_CONFIRMATION"}

    return {"status": "error", "reason": "UNKNOWN_ACTION"}


def run(validated: dict):
    if not validated.get("ok"):
        return {"status": "rejected", "reason": validated.get("error")}

    result = execute(validated["data"])

    log_execution(
        action=validated["data"].get("action"),
        payload=validated["data"],
        result=result
    )

    return result
