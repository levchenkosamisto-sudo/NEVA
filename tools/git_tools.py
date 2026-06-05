import subprocess


def git_status():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )

        branch = result.stdout.strip() or "unknown"

        return {
            "status": "ok",
            "branch": branch
        }

    except Exception as e:
        return {
            "status": "error",
            "reason": str(e)
        }
