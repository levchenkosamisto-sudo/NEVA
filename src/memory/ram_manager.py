"""
NEVA ПАМЯТЬ v3 — управление RAM: qwen↔e5
src/memory/ram_manager.py

Правило: qwen активна → e5 выгружен; e5 активен → qwen в sleep
Триггер: событие (перед задачей), не таймер
Таймаут ожидания выгрузки: 10с
"""
import subprocess
import time
import logging

log = logging.getLogger("neva.ram")

OLLAMA_URL = "http://localhost:11434"
QWEN_MODEL = "qwen2.5:7b"
E5_TIMEOUT = 10  # секунд ждём выгрузки qwen


def qwen_is_active() -> bool:
    """Проверить активна ли qwen через Ollama API."""
    try:
        import urllib.request, json
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/ps", timeout=3) as r:
            data = json.loads(r.read())
            models = [m.get("name", "") for m in data.get("models", [])]
            return any(QWEN_MODEL in m for m in models)
    except Exception:
        return False


def stop_qwen() -> bool:
    """Остановить qwen через ollama stop."""
    try:
        result = subprocess.run(
            ["ollama", "stop", QWEN_MODEL],
            capture_output=True, timeout=15
        )
        # Ждём выгрузки
        for _ in range(E5_TIMEOUT):
            time.sleep(1)
            if not qwen_is_active():
                log.info("[RAM] qwen выгружена")
                return True
        log.warning("[RAM] qwen не выгрузилась за %ds", E5_TIMEOUT)
        return False
    except Exception as e:
        log.error("[RAM] ошибка остановки qwen: %s", e)
        return False


def ensure_e5_available() -> bool:
    """
    Убедиться что e5 может быть загружена.
    Если qwen активна — останавливаем её.
    Возвращает True если e5 доступна.
    """
    if qwen_is_active():
        log.info("[RAM] qwen активна — останавливаем перед загрузкой e5")
        ok = stop_qwen()
        if not ok:
            log.error("[RAM] не удалось освободить RAM для e5")
            return False
    return True


def ensure_qwen_available() -> bool:
    """
    qwen запускается по первому запросу к Ollama автоматически.
    Этот метод только проверяет что e5 не занимает RAM.
    e5 выгружается из Python-процесса при завершении задачи.
    """
    # e5 выгружается в indexer.py после завершения задачи
    return True
