#!/usr/bin/env python3
"""
NEVA Inspector Monitor — терминальный дашборд.
Читает inspector_status.json каждые 10 секунд.
Запуск: python3 neva_inspector_monitor.py
Выход: Q
"""
import json, os, sys, time, threading
from datetime import datetime, timedelta
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
except ImportError:
    print("Установите rich: pip install rich")
    sys.exit(1)

STATUS_FILE = Path.home() / 'Documents/NEVA_MCP_BRIDGE/state/inspector_status.json'
MAINTENANCE = Path.home() / 'Documents/NEVA_MCP_BRIDGE/state/inspector_maintenance'
SUPPRESS    = Path.home() / 'Documents/NEVA_MCP_BRIDGE/state/inspector_suppress_claude'
REFRESH_SEC = 10

console = Console()
_quit = threading.Event()

ICONS = {
    'ALIVE':    ('✅', 'green'),
    'DEAD':     ('💀', 'red bold'),
    'STALE':    ('⚠️', 'yellow'),
    'STARTING': ('🔄', 'cyan'),
    'UNKNOWN':  ('❓', 'dim'),
}

NAMES_RU = {
    'claude_desktop':     'Claude Desktop',
    'neva_medic':         'Medic',
    'neva_mcp_server':    'MCP Server',
    'neva_thermal_guard': 'Thermal Guard',
    'neva_approval':      'Approval Server',
    'background_auditor': 'BG Auditor',
    'neva_control_ctr':   'Control Center',
    'desktop_commander':  'Desktop Commander',
    'ollama':             'Ollama',
    'chrome_cdp':         'Chrome CDP',
}

def fmt_uptime(sec: int | None) -> str:
    if sec is None:
        return '—'
    d = timedelta(seconds=sec)
    h, m = divmod(d.seconds // 60, 60)
    if d.days:
        return f'{d.days}д {h}ч'
    if h:
        return f'{h}ч {m:02d}м'
    return f'{m}м'

def fmt_dead(sec: int | None) -> str:
    if not sec:
        return ''
    return f'мёртв {fmt_uptime(sec)}'

def build_display(data: dict) -> Panel:
    now = datetime.now().strftime('%H:%M:%S')
    age = ''
    try:
        ts = datetime.fromisoformat(data['ts'])
        age_sec = int((datetime.now() - ts).total_seconds())
        age = f'  данные {age_sec}с назад'
        if age_sec > 60:
            age = f'  [red]⚠ ДАННЫЕ УСТАРЕЛИ {age_sec}с[/red]'
    except Exception:
        pass

    # Баннер обслуживания
    banner = ''
    if data.get('maintenance'):
        banner = '\n[yellow blink]⚙ РЕЖИМ ОБСЛУЖИВАНИЯ — действия отключены[/yellow blink]'

    # Таблица программ
    t = Table(box=box.SIMPLE_HEAD, show_edge=False, expand=True)
    t.add_column('Программа',      style='bold', min_width=20)
    t.add_column('Статус',         min_width=10)
    t.add_column('PID',            min_width=8, justify='right')
    t.add_column('Uptime',         min_width=8, justify='right')
    t.add_column('Детали',         min_width=20)

    for name, result in data.get('programs', {}).items():
        status = result.get('status', 'UNKNOWN')
        icon, style = ICONS.get(status, ('❓', 'dim'))
        pid    = str(result['pid']) if result.get('pid') else '—'
        uptime = fmt_uptime(result.get('uptime_sec'))
        detail = fmt_dead(result.get('dead_sec') or result.get('stale_sec'))
        name_ru = NAMES_RU.get(name, name)
        t.add_row(
            name_ru,
            Text(f'{icon} {status}', style=style),
            pid, uptime, detail
        )

    # Система
    sys_data = data.get('system', {})
    sys_line = (
        f"[cyan]swap=[/cyan]{sys_data.get('swap_gb', '?')}GB  "
        f"[cyan]mem=[/cyan]{sys_data.get('mem_pct', '?')}%  "
        f"[cyan]cpu=[/cyan]{sys_data.get('cpu_pct', '?')}%"
    )

    # qwen диагноз
    qwen     = data.get('qwen_diagnosis', '—')
    qwen_ts  = ''
    if data.get('qwen_ts'):
        try:
            qt = datetime.fromisoformat(data['qwen_ts'])
            qwen_ts = f" ({qt.strftime('%H:%M')})"
        except Exception:
            pass
    qwen_line = f'[dim]qwen:[/dim] {qwen}{qwen_ts}'

    header = f'[bold]NEVA Inspector v6[/bold]  {now}{age}{banner}'

    from rich.console import Group
    content = Group(
        Text.from_markup(header),
        Text(''),
        t,
        Text.from_markup(sys_line),
        Text.from_markup(qwen_line),
        Text.from_markup('[dim][M] maintenance  [S] suppress claude  [Q] quit[/dim]'),
    )
    return Panel(content, border_style='blue')

def hotkey_listener():
    """Слушает клавиши в отдельном потоке."""
    import tty, termios
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while not _quit.is_set():
            ch = sys.stdin.read(1).lower()
            if ch == 'q':
                _quit.set()
            elif ch == 'm':
                if MAINTENANCE.exists():
                    MAINTENANCE.unlink()
                else:
                    MAINTENANCE.touch()
            elif ch == 's':
                if SUPPRESS.exists():
                    SUPPRESS.unlink()
                else:
                    SUPPRESS.touch()
    except Exception:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

def main():
    t = threading.Thread(target=hotkey_listener, daemon=True)
    t.start()

    with Live(console=console, refresh_per_second=1, screen=True) as live:
        while not _quit.is_set():
            try:
                if STATUS_FILE.exists():
                    data = json.loads(STATUS_FILE.read_text())
                else:
                    data = {'ts': '', 'programs': {}, 'system': {}}
                live.update(build_display(data))
            except Exception as e:
                live.update(Panel(f'[red]Ошибка чтения статуса: {e}[/red]'))
            time.sleep(REFRESH_SEC)

    console.print('[green]Монитор остановлен.[/green]')

if __name__ == '__main__':
    main()
