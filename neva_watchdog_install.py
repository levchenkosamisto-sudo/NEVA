"""
neva_watchdog_install.py — Установка NEVA как launchd демон
Версия: 3.6 | Архитектор: Claude
Все пути через expanduser — никаких /Users/arka/
KeepAlive только при crash (SuccessfulExit=false)
"""

import os
import sys
import argparse
import logging

logger = logging.getLogger(__name__)

# Динамические пути — не захардкожены
HOME      = os.path.expanduser("~")
NEVA_DIR  = os.path.join(HOME, "Documents", "NEVA")
PLIST_PATH = os.path.join(
    HOME, "Library", "LaunchAgents", "com.neva.server.plist"
)
LOG_DIR   = os.path.join(HOME, "Library", "Logs", "NEVA")

# Python из активного venv или системный
VENV_PYTHON = os.path.join(NEVA_DIR, ".venv", "bin", "python")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable  # текущий python как fallback

PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neva.server</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>neva_context_api:app</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>8000</string>
        <string>--workers</string>
        <string>1</string>
    </array>

    <!-- KeepAlive только при crash — neva stop через launchctl unload работает -->
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>WorkingDirectory</key>
    <string>{neva_dir}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>{neva_dir}</string>
    </dict>

    <key>StandardOutPath</key>
    <string>{log_dir}/neva.log</string>

    <key>StandardErrorPath</key>
    <string>{log_dir}/neva_error.log</string>

    <key>RunAtLoad</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
"""


def install() -> None:
    """Создаёт plist и загружает в launchd."""
    # Создаём директории
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(PLIST_PATH), exist_ok=True)

    # Проверяем что neva_context_api.py существует
    api_file = os.path.join(NEVA_DIR, "neva_context_api.py")
    if not os.path.exists(api_file):
        print(f"❌ Не найден {api_file}")
        print("   Убедись что ТЗ-2 установлен")
        sys.exit(1)

    content = PLIST_TEMPLATE.format(
        python=VENV_PYTHON,
        neva_dir=NEVA_DIR,
        log_dir=LOG_DIR,
    )

    with open(PLIST_PATH, "w") as f:
        f.write(content)

    print(f"✅ plist создан: {PLIST_PATH}")
    print(f"   Python:    {VENV_PYTHON}")
    print(f"   NEVA dir:  {NEVA_DIR}")
    print(f"   Logs:      {LOG_DIR}")

    ret = os.system(f"launchctl load {PLIST_PATH}")
    if ret == 0:
        print("✅ launchd: служба загружена")
    else:
        print(f"⚠️  launchctl load вернул код {ret}")


def uninstall() -> None:
    """Выгружает из launchd и удаляет plist."""
    if os.path.exists(PLIST_PATH):
        ret = os.system(f"launchctl unload {PLIST_PATH}")
        if ret == 0:
            print("✅ launchd: служба выгружена")
        os.remove(PLIST_PATH)
        print(f"✅ plist удалён: {PLIST_PATH}")
    else:
        print(f"⚠️  plist не найден: {PLIST_PATH}")


def status() -> None:
    """Показывает реальный статус службы через launchctl."""
    result = os.popen("launchctl list | grep com.neva.server").read().strip()
    if result:
        parts = result.split("\t")
        pid    = parts[0] if len(parts) > 0 else "?"
        code   = parts[1] if len(parts) > 1 else "?"
        label  = parts[2] if len(parts) > 2 else "?"
        print(f"✅ NEVA RUNNING  pid={pid}  last_exit={code}  label={label}")

        # Попробуем получить K_truth из API
        try:
            import urllib.request
            with urllib.request.urlopen(
                "http://localhost:8000/api/v1/health", timeout=2
            ) as r:
                import json
                data = json.loads(r.read())
                k = data.get("k_truth", "n/a")
                print(f"   K_truth: {k}")
        except Exception:
            print("   API: не отвечает")
    else:
        print("⏹  NEVA STOPPED  (plist не загружен в launchd)")
        if os.path.exists(PLIST_PATH):
            print(f"   plist существует: {PLIST_PATH}")
            print("   Запусти: python neva_watchdog_install.py --install")


def main():
    parser = argparse.ArgumentParser(description="NEVA Watchdog Install")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install",   action="store_true")
    group.add_argument("--uninstall", action="store_true")
    group.add_argument("--status",    action="store_true")
    args = parser.parse_args()

    if args.install:
        install()
    elif args.uninstall:
        uninstall()
    elif args.status:
        status()


if __name__ == "__main__":
    main()
