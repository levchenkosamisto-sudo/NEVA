import json

ALLOWED_ACTIONS = {
    "git_status",
    "file_tree",
    "file_read",
    "system_info",
    "run_playbook",
    "diagnostics",
    "run_tests",
    "ollama_list",
    "ollama_run"
}

READONLY_ACTIONS = {
    "git_status",
    "file_tree",
    "file_read",
    "system_info"
}


def validate(raw: str):
    try:
        data = json.loads(raw)
    except Exception:
        return {"ok": False, "error": "INVALID_JSON"}

    action = data.get("action")

    if not action:
        return {"ok": False, "error": "NO_ACTION"}

    if action not in ALLOWED_ACTIONS:
        return {"ok": False, "error": "ACTION_NOT_ALLOWED"}

    data["readonly"] = action in READONLY_ACTIONS

    return {"ok": True, "data": data}
