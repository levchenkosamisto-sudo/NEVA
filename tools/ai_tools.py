import subprocess

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

def ollama_run(model: str, prompt: str):
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            timeout=120
        )
        return {"status": "ok", "output": result.stdout}
    except Exception as e:
        return {"status": "error", "reason": str(e)}
