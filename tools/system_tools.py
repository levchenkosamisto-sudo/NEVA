import subprocess
import os

def file_read(path: str):
    try:
        with open(path, "r") as f:
            return {"status": "ok", "content": f.read()}
    except Exception as e:
        return {"status": "error", "reason": str(e)}

def run_tests():
    try:
        result = subprocess.run(
            ["pytest", "-q"],
            capture_output=True,
            text=True,
            timeout=60
        )
        return {
            "status": "ok",
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}

def ollama_list():
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
