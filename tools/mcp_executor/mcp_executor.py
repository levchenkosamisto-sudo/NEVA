import os
import subprocess
import time
import sys

from graph.execution_logger import log_execution

BASE_DIR = os.path.realpath(os.path.expanduser("~/Documents/NEVA_MCP_BRIDGE"))

# Подключаем реальные инструменты из NEVA
NEVA_TOOLS = os.path.realpath(os.path.expanduser("~/Documents/NEVA/tools"))
if NEVA_TOOLS not in sys.path:
    sys.path.insert(0, NEVA_TOOLS)

try:
    from git_tools import git_status as _git_status
    GIT_TOOLS_OK = True
except ImportError:
    GIT_TOOLS_OK = False

try:
    from system_tools import file_read as _file_read, run_tests as _run_tests, ollama_list as _ollama_list
    SYSTEM_TOOLS_OK = True
except ImportError:
    SYSTEM_TOOLS_OK = False


def safe_path(path: str):
    if not path:
        return None
    candidate = os.path.abspath(os.path.join(BASE_DIR, path.lstrip('/')))
    if candidate.startswith(BASE_DIR + os.sep) or candidate == BASE_DIR:
        return candidate
    return None


def execute(command: dict):
    action = command.get("action")

    if action == "git_status":
        if GIT_TOOLS_OK:
            return {"status": "ok", "action": action, "result": _git_status()}
        # fallback
        try:
            r = subprocess.run(
                ["git", "-C", os.path.expanduser("~/Documents/NEVA"), "status", "--short", "--branch"],
                capture_output=True, text=True, timeout=10
            )
            return {"status": "ok", "action": action, "result": r.stdout}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    if action == "file_tree":
        try:
            result = []
            for root, dirs, files in os.walk(BASE_DIR):
                # Пропускаем скрытые и __pycache__
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
                level = root.replace(BASE_DIR, '').count(os.sep)
                indent = '  ' * level
                folder = os.path.basename(root)
                result.append(f"{indent}{folder}/")
                sub_indent = '  ' * (level + 1)
                for file in files:
                    if not file.startswith('.'):
                        result.append(f"{sub_indent}{file}")
            return {"status": "ok", "action": action, "result": "\n".join(result[:200])}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    if action == "file_read":
        path = safe_path(command.get("params", {}).get("path", ""))
        if not path:
            return {"status": "blocked", "reason": "PATH_ESCAPE_BLOCKED"}
        if SYSTEM_TOOLS_OK:
            # Передаём относительный путь от BASE_DIR
            rel_path = os.path.relpath(path, BASE_DIR)
            return {"status": "ok", "action": action, "file": path, "content": _file_read(path)}
        try:
            with open(path, 'r', errors='replace') as f:
                content = f.read(50000)  # max 50KB
            return {"status": "ok", "action": action, "file": path, "content": content}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    if action == "system_info":
        try:
            import platform
            import psutil
            return {
                "status": "ok",
                "action": action,
                "result": {
                    "platform": platform.platform(),
                    "python": platform.python_version(),
                    "ram_pct": psutil.virtual_memory().percent,
                    "cpu_pct": psutil.cpu_percent(interval=0.5),
                    "base_dir": BASE_DIR,
                }
            }
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    if action == "run_playbook":
        name = command.get("params", {}).get("name")
        if name == "diagnostics":
            try:
                r = subprocess.run(
                    [sys.executable,
                     os.path.expanduser("~/Documents/NEVA/neva_self_diagnostics.py"),
                     "--health"],
                    capture_output=True, text=True, timeout=10,
                    cwd=os.path.expanduser("~/Documents/NEVA")
                )
                return {"status": "ok", "playbook": "diagnostics", "result": r.stdout}
            except Exception as e:
                return {"status": "error", "reason": str(e)}
        return {"status": "blocked", "reason": "UNKNOWN_PLAYBOOK"}

    if action == "run_tests":
        if SYSTEM_TOOLS_OK:
            return _run_tests()
        try:
            r = subprocess.run(
                ["pytest", "--tb=short", "-q"],
                capture_output=True, text=True, timeout=60,
                cwd=os.path.expanduser("~/Documents/NEVA")
            )
            return {"status": "ok", "output": r.stdout[-2000:], "errors": r.stderr[-1000:]}
        except subprocess.TimeoutExpired:
            return {"status": "blocked", "reason": "TIMEOUT"}

    if action == "ollama_list":
        if SYSTEM_TOOLS_OK:
            return _ollama_list()
        try:
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
            return {"status": "ok", "output": r.stdout}
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
