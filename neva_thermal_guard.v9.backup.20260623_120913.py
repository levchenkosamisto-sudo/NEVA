#!/usr/bin/env python3
"""
NEVA-TASK-008 — Thermal Guard v9
Управляющая система защиты Mac M1 от перегрева.
Режим MVP: ollama_only — управляет только моделями Ollama.

Автор: Claude (архитектор NEVA)
Директор: Серж
Утверждено: 2026-06-06
"""

import json
import logging
import logging.handlers
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import psutil

# ─── Пути ────────────────────────────────────────────────────────────────────
BASE_DIR    = Path('~/Documents/NEVA').expanduser()
STATE_PATH  = BASE_DIR / 'thermal_state.json'
STATE_DIR   = str(BASE_DIR)
LOG_PATH    = BASE_DIR / 'thermal.log'
CONFIG_PATH = BASE_DIR / 'thermal_guard_config.json'
DISABLE_FLAG = BASE_DIR / 'thermal_guard.disabled'

STATE_MAX_SIZE_BYTES = 64 * 1024   # 64 KB
POWERMETRICS_STALE_SEC = 1.0       # медленнее → данные устаревшие
HOT_PENDING_MAX_WALL_GAP_SEC = 60  # после сна — сбросить HOT_PENDING

# ─── FSM ─────────────────────────────────────────────────────────────────────
FSM_TRANSITIONS = {
    'NOMINAL':       ['WARM', 'DEGRADED'],
    'WARM':          ['NOMINAL', 'HOT_PENDING', 'DEGRADED'],
    'HOT_PENDING':   ['WARM', 'HOT', 'CRITICAL', 'DEGRADED'],
    'HOT':           ['WARM', 'CRITICAL', 'BLOCKED', 'DEGRADED'],
    'CRITICAL':      ['BLOCKED', 'HOT', 'DEGRADED'],
    'BLOCKED':       ['UNBLOCKING', 'DEGRADED'],
    'UNBLOCKING':    ['NOMINAL', 'HOT', 'BLOCKED'],
    'DEGRADED':      ['NOMINAL', 'DEGRADED_HIGH', 'BLOCKED'],
    'DEGRADED_HIGH': ['BLOCKED', 'DEGRADED'],
}

# ─── Значения по умолчанию ────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "mode": "ollama_only",
    "thresholds": {
        "WARM_TEMP_C": 75,
        "HOT_TEMP_C": 83,
        "CRITICAL_TEMP_C": 90,
        "RECOVERY_TEMP_FALL_C": 67,
        "RECOVERY_TEMP_CANCEL_C": 72,
        "SWAP_WARN_RISE_GB": 2.0,
        "SWAP_WARN_FALL_GB": 1.5,
        "DEGRADED_HIGH_SWAP_GB": 3.0,
        "DEGRADED_HIGH_MEM_PCT": 88,
        "RECOVERY_SWAP_MAX_GB": 2.0,
        "RECOVERY_MEM_FALL_PCT": 82,
    },
    "hot_stability_sec": 5,
    "poll_nominal_sec": 30,
    "poll_active_sec": 10,
    "poll_pending_sec": 2,
    "recovery_hysteresis_sec": 60,
    "hot_cascade_wait_sec": 30,
    "cooldown_after_unload_sec": 120,
    "cooldown_max_sec": 600,
    "minimum_unblock_interval_sec": 300,
    "config_reload_sec": 60,
    "max_notify_critical": 3,
    "notify_repeat_min": 10,
    "notify_reset_after_min": 60,
    "max_notify_degraded": 3,
    "max_notify_dirs": 3,
    "disk_free_min_mb": 100,
    "pending_timeout_sec": 120,
    "max_corrupted_backups": 5,
    "ollama_restart_after_crash": False,
}

DEFAULT_STATE = {
    "schema_version": 1,
    "state": "NOMINAL",
    "temp_c": None,
    "swap_gb": 0.0,
    "mem_pct": 0.0,
    "memory_pressure_high": False,
    "mode": "ollama_only",
    "ollama_available": True,
    "ollama_serve_up": True,
    "powermetrics_available": True,
    "stopped_models": [],
    "pending_operation": None,
    "pending_created_wall": None,
    "cooldown_until_wall": None,
    "last_unblock_wall": None,
    "current_cooldown_sec": 120,
    "hot_pending_since_wall": None,
    "last_event": None,
}

# ─── Парсинг температуры ──────────────────────────────────────────────────────
TEMP_PATTERNS = [
    r'CPU die temperature:\s*([\d.]+)',
    r'GPU die temperature:\s*([\d.]+)',
    r'ANE temperature:\s*([\d.]+)',
]

def parse_max_temp(output):
    temps = []
    for p in TEMP_PATTERNS:
        m = re.search(p, output, re.IGNORECASE)
        if m:
            temps.append(float(m.group(1)))
    return max(temps) if temps else None

def _powermetrics_worker(result_queue):
    try:
        if not os.path.exists('/usr/bin/powermetrics'):
            result_queue.put(('error', 'powermetrics not found', 0))
            return
        start = time.monotonic()
        r = subprocess.run(
            ['sudo', 'powermetrics', '--samplers', 'smc', '-n', '1'],
            capture_output=True, text=True, timeout=7
        )
        duration = time.monotonic() - start
        if r.returncode != 0:
            result_queue.put(('error',
                f"returncode={r.returncode} {r.stderr[:200]}", duration))
        else:
            result_queue.put(('ok', parse_max_temp(r.stdout), duration))
    except subprocess.TimeoutExpired:
        result_queue.put(('timeout', None, 7.0))
    except PermissionError as e:
        result_queue.put(('error', f"PermissionError: {e}", 0))
    except Exception as e:
        result_queue.put(('error', str(e), 0))


# ─── Основной класс ───────────────────────────────────────────────────────────
class ThermalGuard:

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self._setup_logging()
        self.logger = logging.getLogger('thermal_guard')
        self.config = DEFAULT_CONFIG.copy()
        self.state = DEFAULT_STATE.copy()
        self._last_config_reload = 0.0
        self._last_cycle_time = time.monotonic()
        self._recovery_start = None
        self._notify_counts = {}
        self._notify_critical_count = 0
        self._notify_critical_first = 0.0
        self._notify_critical_last = 0.0
        self._disable_notified = False
        self.last_temp = None
        self.last_swap = 0.0

    # ─── Логирование ─────────────────────────────────────────────────────────
    def _setup_logging(self):
        logger = logging.getLogger('thermal_guard')
        logger.setLevel(logging.DEBUG)
        handler = logging.handlers.RotatingFileHandler(
            str(LOG_PATH), maxBytes=10*1024*1024, backupCount=3
        )
        fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s',
                                 datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        if self.dry_run or '--self-test' in sys.argv:
            logger.addHandler(logging.StreamHandler(sys.stdout))

    # ─── Конфигурация ─────────────────────────────────────────────────────────
    def _validate_config(self, config):
        t = config.get('thresholds', {})
        errors = []
        checks = [
            (t.get('HOT_TEMP_C', 0),      '>',  t.get('WARM_TEMP_C', 0),
             'HOT_TEMP_C > WARM_TEMP_C'),
            (t.get('CRITICAL_TEMP_C', 0), '>',  t.get('HOT_TEMP_C', 0),
             'CRITICAL_TEMP_C > HOT_TEMP_C'),
            (t.get('RECOVERY_TEMP_FALL_C', 0), '<', t.get('WARM_TEMP_C', 0),
             'RECOVERY_TEMP_FALL_C < WARM_TEMP_C'),
            (t.get('RECOVERY_TEMP_CANCEL_C', 0), '<', t.get('HOT_TEMP_C', 0),
             'RECOVERY_TEMP_CANCEL_C < HOT_TEMP_C'),
            (t.get('SWAP_WARN_FALL_GB', 0), '<', t.get('SWAP_WARN_RISE_GB', 0),
             'SWAP_WARN_FALL_GB < SWAP_WARN_RISE_GB'),
            (t.get('RECOVERY_MEM_FALL_PCT', 0), '<', t.get('DEGRADED_HIGH_MEM_PCT', 0),
             'RECOVERY_MEM_FALL_PCT < DEGRADED_HIGH_MEM_PCT'),
        ]
        ops = {'>': lambda a,b: a>b, '<': lambda a,b: a<b}
        for a, op, b, msg in checks:
            if not ops[op](a, b):
                errors.append(msg)
        if config.get('cooldown_max_sec', 0) < config.get('cooldown_after_unload_sec', 0):
            errors.append('cooldown_max_sec >= cooldown_after_unload_sec')
        if errors:
            for e in errors:
                logging.getLogger('thermal_guard').error(f"CONFIG ERROR: {e}")
            return False
        return True

    def _load_config(self):
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            if self._validate_config(cfg):
                return cfg
        except FileNotFoundError:
            pass
        except Exception as e:
            self.logger.error(f"config load error: {e}")
        return DEFAULT_CONFIG.copy()

    def _refresh_config(self):
        now = time.monotonic()
        if now - self._last_config_reload < self.config.get('config_reload_sec', 60):
            return
        new_cfg = self._load_config()
        self.config = new_cfg
        self._last_config_reload = now

    # ─── Состояние ───────────────────────────────────────────────────────────
    def _write_state(self, state):
        if self.dry_run:
            self.logger.info(f"[DRY-RUN] state: {state.get('state')}")
            return True
        try:
            stat_info = os.statvfs(STATE_DIR)
            free_mb = (stat_info.f_frsize * stat_info.f_bavail) / (1024*1024)
            if free_mb < self.config.get('disk_free_min_mb', 100):
                self.logger.error(f"DISK: {free_mb:.0f}MB < минимума")
                self._notify("Мало места на диске")
                return False
            with tempfile.NamedTemporaryFile('w', dir=STATE_DIR,
                    delete=False, suffix='.tmp') as f:
                json.dump(state, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
                tmp = f.name
            os.replace(tmp, STATE_PATH)
            dir_fd = os.open(STATE_DIR, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            return True
        except Exception as e:
            self.logger.error(f"_write_state failed: {e}")
            try:
                if 'tmp' in locals() and os.path.exists(tmp):
                    os.unlink(tmp)
            except Exception:
                pass
            return False

    def _load_state(self):
        if not os.path.exists(STATE_PATH):
            return DEFAULT_STATE.copy()
        try:
            size = os.path.getsize(STATE_PATH)
        except OSError as e:
            self.logger.error(f"getsize error: {e}")
            return DEFAULT_STATE.copy()
        if size == 0:
            self._backup_corrupted('empty')
            return DEFAULT_STATE.copy()
        if size > STATE_MAX_SIZE_BYTES:
            self.logger.error(f"STATE oversized: {size}")
            self._backup_corrupted('oversized')
            return DEFAULT_STATE.copy()
        try:
            with open(STATE_PATH, encoding='utf-8') as f:
                state = json.load(f)
            if state.get('schema_version', 0) < 1:
                state['schema_version'] = 1
            return state
        except json.JSONDecodeError as e:
            self.logger.error(f"STATE JSON: {e}")
            self._backup_corrupted('json_error')
        except UnicodeDecodeError as e:
            self.logger.error(f"STATE encoding: {e}")
            self._backup_corrupted('encoding_error')
        except PermissionError as e:
            self.logger.error(f"STATE permission: {e}")
            self._notify("Guard: нет доступа к thermal_state.json")
        except OSError as e:
            self.logger.error(f"STATE OSError: {e}")
            self._backup_corrupted('oserror')
        return DEFAULT_STATE.copy()

    def _backup_corrupted(self, reason='unknown'):
        try:
            if os.path.exists(STATE_PATH) and os.access(STATE_PATH, os.R_OK):
                backup = f"{STATE_PATH}.corrupted.{int(time.time())}"
                shutil.copy(str(STATE_PATH), backup)
                self.logger.error(f"STATE CORRUPTED ({reason}) → {backup}")
                backups = sorted(
                    Path(STATE_DIR).glob('thermal_state.json.corrupted.*'),
                    key=lambda p: p.stat().st_mtime
                )
                max_b = self.config.get('max_corrupted_backups', 5)
                while len(backups) > max_b:
                    try:
                        backups[0].unlink()
                        backups.pop(0)
                    except OSError:
                        break
            else:
                self.logger.error(f"STATE CORRUPTED ({reason}): backup невозможен")
        except Exception as e:
            self.logger.error(f"backup failed: {e}")
        self._notify("thermal_state.json повреждён, Guard начат с чистого состояния")

    # ─── FSM переход ─────────────────────────────────────────────────────────
    def _transition(self, new_state):
        current = self.state['state']
        allowed = FSM_TRANSITIONS.get(current, [])
        if new_state not in allowed:
            self.logger.error(f"FSM BLOCKED: {current}→{new_state} запрещено")
            return False
        new_obj = dict(self.state)
        new_obj['state'] = new_state
        new_obj['last_event'] = datetime.now().isoformat()
        if not self._write_state(new_obj):
            self.logger.error(f"FSM: запись не удалась, переход {new_state} отменён")
            return False
        self.state.update(new_obj)
        self.logger.info(f"FSM: {current} → {new_state}")
        return True

    # ─── Температура ─────────────────────────────────────────────────────────
    def _read_temp(self):
        """Возвращает (float|None, is_stale: bool)"""
        q = multiprocessing.Queue()
        p = multiprocessing.Process(target=_powermetrics_worker, args=(q,))
        p.start()
        p.join(timeout=8)
        if p.is_alive():
            p.terminate()
            p.join(timeout=2)
            if p.is_alive():
                p.kill()
                p.join()
            q.close(); q.join_thread()
            self.logger.warning("powermetrics: процесс убит принудительно")
            return None, True
        if q.empty():
            q.close(); q.join_thread()
            return None, True
        result = q.get_nowait()
        q.close(); q.join_thread()
        status = result[0]
        if status == 'ok':
            temp, duration = result[1], result[2]
            is_stale = duration > POWERMETRICS_STALE_SEC
            if is_stale:
                self.logger.warning(f"powermetrics медленно ({duration:.1f}с)")
            return temp, is_stale
        elif status == 'error':
            self.logger.error(f"powermetrics error: {result[1]}")
            return None, True
        return None, True

    # ─── Память ──────────────────────────────────────────────────────────────
    def _read_memory(self):
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        thr = self.config['thresholds']
        return {
            'mem_pct': mem.percent,
            'swap_gb': swap.used / (1024**3),
            'memory_pressure_high': mem.percent >= thr['DEGRADED_HIGH_MEM_PCT'],
        }

    # ─── HOT_PENDING ─────────────────────────────────────────────────────────
    def _handle_hot_pending(self, temp):
        now = time.time()
        since = self.state.get('hot_pending_since_wall')
        stability = self.config.get('hot_stability_sec', 5)

        if since is None:
            self.state['hot_pending_since_wall'] = now
            self._write_state(self.state)
            self.logger.info(f"HOT_PENDING начат: temp={temp}°C")
            return False

        elapsed = now - since

        if elapsed < 0:
            self.logger.warning("HOT_PENDING: время назад, сброс")
            self.state['hot_pending_since_wall'] = now
            self._write_state(self.state)
            return False

        if elapsed > stability + HOT_PENDING_MAX_WALL_GAP_SEC:
            self.logger.info(f"HOT_PENDING: gap={elapsed:.0f}с (sleep?), сброс")
            self.state['hot_pending_since_wall'] = now
            self._write_state(self.state)
            return False

        if elapsed >= stability:
            return True

        self.logger.debug(f"HOT_PENDING: {elapsed:.1f}с/{stability}с")
        return False

    def _reset_hot_pending(self):
        if self.state.get('hot_pending_since_wall') is not None:
            self.state['hot_pending_since_wall'] = None
            self._write_state(self.state)

    # ─── Уровень угрозы ──────────────────────────────────────────────────────
    def _determine_level(self, temp, swap_gb, mem_pct):
        thr = self.config['thresholds']

        if temp is None:
            self.state['powermetrics_available'] = False
            self._reset_hot_pending()
            if (swap_gb >= thr['DEGRADED_HIGH_SWAP_GB'] or
                    mem_pct >= thr['DEGRADED_HIGH_MEM_PCT']):
                return 'DEGRADED_HIGH'
            return 'DEGRADED'

        self.state['powermetrics_available'] = True

        if temp >= thr['CRITICAL_TEMP_C']:
            self._reset_hot_pending()
            return 'CRITICAL'

        if temp >= thr['HOT_TEMP_C']:
            if self._handle_hot_pending(temp):
                return 'HOT'
            return 'HOT_PENDING'

        self._reset_hot_pending()

        current = self.state['state']
        if current == 'WARM':
            if (temp < thr['WARM_TEMP_C'] - 3 and
                    swap_gb < thr['SWAP_WARN_FALL_GB']):
                return 'NOMINAL'
            return 'WARM'
        else:
            if (temp >= thr['WARM_TEMP_C'] or
                    swap_gb >= thr['SWAP_WARN_RISE_GB']):
                return 'WARM'
        return 'NOMINAL'

    # ─── Ollama ───────────────────────────────────────────────────────────────
    def _find_ollama_process(self):
        try:
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (p.info.get('name') or '').lower()
                    cmdline = ' '.join(p.info.get('cmdline') or []).lower()
                    if name == 'ollama' or 'ollama serve' in cmdline:
                        return p
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            self.logger.warning(f"process_iter: {e}")
        return None

    def _check_ollama_serve(self):
        try:
            urllib.request.urlopen('http://localhost:11434/api/tags', timeout=2)
            self.state['ollama_serve_up'] = True
            return True
        except Exception:
            pass
        proc = self._find_ollama_process()
        if proc is None:
            self.logger.error("OLLAMA SERVE: процесс не найден")
            self._notify_limited('ollama_crash', "Ollama serve не запущен")
            if self.config.get('ollama_restart_after_crash', False):
                uid = os.getuid()
                if uid != 0:
                    subprocess.run(
                        ['launchctl', 'kickstart', '-kp',
                         f'gui/{uid}/com.ollama.ollama'],
                        capture_output=True
                    )
        else:
            self.logger.warning(f"OLLAMA: процесс жив (PID={proc.pid}), API молчит")
        self.state['ollama_serve_up'] = False
        return False

    def _is_model_loaded(self, model_name):
        time.sleep(0.5)
        try:
            req = urllib.request.Request('http://localhost:11434/api/tags')
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                for m in data.get('models', []):
                    if m['name'] == model_name:
                        return m.get('size_vram', 0) > 0
        except Exception:
            return False
        return False

    def _get_loaded_models(self):
        try:
            req = urllib.request.Request('http://localhost:11434/api/tags')
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                return [m['name'] for m in data.get('models', [])
                        if m.get('size_vram', 0) > 0]
        except Exception:
            return []

    def _update_ollama_available(self):
        cooldown = time.time() < (self.state.get('cooldown_until_wall') or 0)
        has_stopped = len(self.state.get('stopped_models', [])) > 0
        pending = self.state.get('pending_operation') is not None
        self.state['ollama_available'] = not (cooldown or has_stopped or pending)

    def _sync_state_with_reality(self):
        """Вызывать только в состоянии BLOCKED"""
        if not self.state.get('stopped_models'):
            return
        loaded = self._get_loaded_models()
        actual = [m for m in self.state['stopped_models'] if m not in loaded]
        if len(actual) != len(self.state['stopped_models']):
            self.logger.info(f"sync: {self.state['stopped_models']}→{actual}")
            self.state['stopped_models'] = actual
            self._update_ollama_available()
            self._write_state(self.state)

    def _unload_model(self, model_name):
        self.state['pending_operation'] = {
            'action': f'unload_{model_name.replace(":", "_")}',
            'started_at': datetime.now().isoformat()
        }
        self.state['pending_created_wall'] = time.time()
        self.state['ollama_available'] = False
        self._write_state(self.state)

        self.logger.info(f"ACTION_START unload {model_name} "
                         f"temp={self.last_temp} swap={self.last_swap:.1f}GB")

        if not self._is_model_loaded(model_name):
            self.logger.info(f"{model_name} уже не загружена")
            self.state['pending_operation'] = None
            self.state['pending_created_wall'] = None
            if model_name not in self.state['stopped_models']:
                self.state['stopped_models'].append(model_name)
            self._update_ollama_available()
            self._write_state(self.state)
            return True

        try:
            data = json.dumps({'model': model_name, 'keep_alive': 0}).encode()
            req = urllib.request.Request(
                'http://localhost:11434/api/generate',
                data=data, method='POST'
            )
            urllib.request.urlopen(req, timeout=10)
            self.logger.info(f"ACTION_SUCCESS unload {model_name}")
            if model_name not in self.state['stopped_models']:
                self.state['stopped_models'].append(model_name)
            self.state['pending_operation'] = None
            self.state['pending_created_wall'] = None
            self.state['cooldown_until_wall'] = (
                time.time() + self.state.get('current_cooldown_sec',
                    self.config['cooldown_after_unload_sec'])
            )
            self._update_ollama_available()
            self._write_state(self.state)
            return True
        except Exception as e:
            self.logger.error(f"ACTION_FAILED unload {model_name}: {e}")
            self._notify_limited('unload_fail',
                f"Не удалось выгрузить {model_name}")
            return False

    # ─── Cooldown и UNBLOCK ───────────────────────────────────────────────────
    def _restore_cooldown(self):
        wall = self.state.get('cooldown_until_wall') or 0
        if wall and time.time() < wall:
            remaining = wall - time.time()
            self.logger.info(f"Cooldown восстановлен: осталось {remaining:.0f}с")
            self.state['ollama_available'] = False
        else:
            self._update_ollama_available()

    def _adaptive_cooldown(self):
        now = time.time()
        last = self.state.get('last_unblock_wall') or 0
        min_interval = self.config.get('minimum_unblock_interval_sec', 300)
        base = self.config.get('cooldown_after_unload_sec', 120)
        max_cd = self.config.get('cooldown_max_sec', 600)
        if last > 0 and now - last < min_interval:
            new_cd = min(self.state.get('current_cooldown_sec', base) + 60, max_cd)
            self.state['current_cooldown_sec'] = new_cd
            self.logger.warning(f"Rapid reheat: cooldown → {new_cd}с")
        else:
            self.state['current_cooldown_sec'] = base

    def _do_unblock(self):
        if not self._transition('UNBLOCKING'):
            return
        thr = self.config['thresholds']
        temp, _ = self._read_temp()
        mem = self._read_memory()

        if temp is not None and temp >= thr['RECOVERY_TEMP_CANCEL_C']:
            self.logger.info(f"UNBLOCK отменён: temp={temp}°C")
            self._transition('HOT')
            return

        if (mem['swap_gb'] >= thr['RECOVERY_SWAP_MAX_GB'] or
                mem['mem_pct'] >= thr['RECOVERY_MEM_FALL_PCT']):
            self.logger.info(f"UNBLOCK отложен: swap={mem['swap_gb']:.1f} "
                             f"mem={mem['mem_pct']:.0f}%")
            self._transition('BLOCKED')
            return

        if not self._check_ollama_serve():
            self.logger.warning("UNBLOCK отложен: ollama serve недоступен")
            self._transition('BLOCKED')
            return

        self._adaptive_cooldown()
        self.state['stopped_models'] = []
        self.state['last_unblock_wall'] = time.time()
        self._update_ollama_available()
        self._transition('NOMINAL')
        self._reset_notify_key('degraded')
        self._reset_notify_key('ollama_crash')
        self._notify("Ollama разблокирована. Модели загрузятся при запросе (~20с)")
        self.logger.info("UNBLOCK завершён")

    # ─── Действия по уровням ─────────────────────────────────────────────────
    def _act(self, level):
        current = self.state['state']

        if level == 'NOMINAL':
            if current not in ('NOMINAL', 'WARM'):
                self._transition('NOMINAL') if current == 'WARM' else None

        elif level == 'WARM':
            if current == 'NOMINAL':
                self._transition('WARM')
            elif current == 'HOT_PENDING':
                self._transition('WARM')

        elif level == 'HOT_PENDING':
            if current == 'WARM':
                self._transition('HOT_PENDING')
            elif current == 'NOMINAL':
                self._transition('WARM')
                self._transition('HOT_PENDING')

        elif level == 'HOT':
            if current == 'HOT_PENDING':
                self._transition('HOT')
            if self.state['state'] == 'HOT':
                self._do_hot()

        elif level == 'CRITICAL':
            if current not in ('CRITICAL', 'BLOCKED'):
                self._transition('CRITICAL')
            if self.state['state'] == 'CRITICAL':
                self._do_critical()

        elif level in ('DEGRADED', 'DEGRADED_HIGH'):
            if current not in ('DEGRADED', 'DEGRADED_HIGH', 'BLOCKED'):
                self._transition('DEGRADED')
            if level == 'DEGRADED_HIGH' and self.state['state'] == 'DEGRADED':
                self._transition('DEGRADED_HIGH')
            if self.state['state'] == 'DEGRADED':
                self._notify_limited('degraded',
                    "Guard: powermetrics недоступен, работаем без температуры")
            elif self.state['state'] == 'DEGRADED_HIGH':
                self._do_degraded_high()

        # BLOCKED → проверить UNBLOCK
        if self.state['state'] == 'BLOCKED':
            self._check_unblock()

    def _do_hot(self):
        thr = self.config['thresholds']
        self.logger.info("HOT: начинаем каскадную выгрузку")
        # Шаг 1: qwen2.5:7b
        self._unload_model('qwen2.5:7b')
        self._transition('BLOCKED')

        # Шаг 2: ждать и проверить
        cascade_wait = self.config.get('hot_cascade_wait_sec', 30)
        self.logger.info(f"HOT: ждём {cascade_wait}с...")
        time.sleep(cascade_wait)

        temp2, _ = self._read_temp()
        if temp2 is not None and temp2 >= thr['HOT_TEMP_C']:
            self.logger.info(f"HOT cascade: temp={temp2}°C, выгружаем llama3.2:3b")
            self._unload_model('llama3.2:3b')
        else:
            self.logger.info(f"HOT cascade: temp={temp2}°C упала, llama не трогаем")

    def _do_critical(self):
        self.logger.info("CRITICAL: выгружаем все модели")
        for model in ['qwen2.5:7b', 'llama3.2:3b']:
            self._unload_model(model)
        self._transition('BLOCKED')
        self._notify_critical("CRITICAL: все модели Ollama выгружены")

    def _do_degraded_high(self):
        self.logger.info("DEGRADED_HIGH: выгружаем qwen по давлению памяти")
        self._unload_model('qwen2.5:7b')
        self._transition('BLOCKED')

    def _check_unblock(self):
        thr = self.config['thresholds']
        cooldown_wall = self.state.get('cooldown_until_wall') or 0
        if time.time() < cooldown_wall:
            return  # cooldown ещё активен

        if self._recovery_start is None:
            self._recovery_start = time.monotonic()
            return

        elapsed = time.monotonic() - self._recovery_start
        hysteresis = self.config.get('recovery_hysteresis_sec', 60)
        if elapsed < hysteresis:
            return

        self._recovery_start = None
        self._do_unblock()

    # ─── Pending timeout ──────────────────────────────────────────────────────
    def _check_pending_timeout(self):
        if not self.state.get('pending_operation'):
            return
        created = self.state.get('pending_created_wall') or 0
        timeout = self.config.get('pending_timeout_sec', 120)
        if time.time() - created > timeout:
            action = (self.state['pending_operation'] or {}).get('action', '')
            self.logger.error(f"pending timeout: {action}")
            self.state['pending_operation'] = None
            self.state['pending_created_wall'] = None
            self._update_ollama_available()
            self._write_state(self.state)
            self._notify_limited('pending_timeout',
                f"Операция {action} зависла и сброшена")

    # ─── Pending при старте ───────────────────────────────────────────────────
    def _resolve_pending_on_start(self):
        pending = self.state.get('pending_operation')
        if not pending:
            return
        action = pending.get('action', '')
        created = self.state.get('pending_created_wall') or 0
        if time.time() - created > 600:
            self.logger.error(f"pending устарел (>10 мин): {action}")
            self.state['pending_operation'] = None
            self.state['pending_created_wall'] = None
            self._update_ollama_available()
            self._write_state(self.state)
            return
        if 'unload' in action:
            model = action.replace('unload_', '').replace('_', ':')
            if not self._is_model_loaded(model):
                self.logger.info(f"pending: {model} выгружена, закрываем")
                if model not in self.state['stopped_models']:
                    self.state['stopped_models'].append(model)
                self.state['pending_operation'] = None
                self.state['pending_created_wall'] = None
                self._update_ollama_available()
            else:
                self.logger.info(f"pending: {model} ещё загружена, повторяем")
                self._unload_model(model)
        self._write_state(self.state)

    # ─── Sleep/Wake ───────────────────────────────────────────────────────────
    def _detect_sleep_wake(self):
        now = time.monotonic()
        gap = now - self._last_cycle_time
        if gap > 300:
            self.logger.info(f"Sleep/wake: {gap:.0f}с, сброс таймеров")
            self._recovery_start = None
            self._disable_notified = False
        self._last_cycle_time = now

    # ─── Уведомления ─────────────────────────────────────────────────────────
    def _notify(self, message):
        if self.dry_run:
            self.logger.info(f"[DRY-RUN] notify: {message}")
            return
        try:
            subprocess.run(
                ['osascript', '-e',
                 f'display notification "{message}" with title "NEVA Thermal Guard"'],
                capture_output=True, timeout=5
            )
        except Exception as e:
            self.logger.error(f"osascript: {e}")

    def _notify_limited(self, key, message, max_count=None):
        if not hasattr(self, '_notify_counts'):
            self._notify_counts = {}
        count = self._notify_counts.get(key, 0)
        limit = max_count or self.config.get(f'max_notify_{key}', 3)
        if count >= limit:
            return
        self._notify(message)
        self._notify_counts[key] = count + 1

    def _reset_notify_key(self, key):
        if hasattr(self, '_notify_counts'):
            self._notify_counts.pop(key, None)

    def _notify_critical(self, message):
        now = time.monotonic()
        max_c = self.config.get('max_notify_critical', 3)
        repeat_sec = self.config.get('notify_repeat_min', 10) * 60
        reset_sec = self.config.get('notify_reset_after_min', 60) * 60

        if self.state['state'] not in ('CRITICAL', 'BLOCKED'):
            self._notify_critical_count = 0

        if self._notify_critical_count == 0:
            self._notify_critical_first = now

        if now - self._notify_critical_first > reset_sec:
            self._notify_critical_count = 0
            self._notify_critical_first = now

        if self._notify_critical_count >= max_c:
            if now - self._notify_critical_last < repeat_sec:
                return

        self._notify(message)
        self._notify_critical_count += 1
        self._notify_critical_last = now

    # ─── Dirs ─────────────────────────────────────────────────────────────────
    def _check_dirs(self):
        notified = 0
        while not BASE_DIR.exists():
            if notified < self.config.get('max_notify_dirs', 3):
                self._notify(f"NEVA Guard: каталог {BASE_DIR} не найден")
                self.logger.critical(f"Каталог не найден: {BASE_DIR}, жду...")
                notified += 1
            time.sleep(60)

    # ─── Self-test ────────────────────────────────────────────────────────────
    def run_self_test(self):
        print("=== NEVA Thermal Guard v9 — Self-test ===\n")
        results = {}

        # 1. powermetrics
        temp, stale = self._read_temp()
        results['1_powermetrics'] = (
            f'PASS (temp={temp}°C stale={stale})'
            if temp is not None else 'FAIL: температура не получена'
        )

        # 2. psutil
        try:
            list(psutil.process_iter(['name']))
            psutil.swap_memory()
            results['2_psutil'] = 'PASS'
        except Exception as e:
            results['2_psutil'] = f'FAIL: {e}'

        # 3. osascript
        try:
            subprocess.run(
                ['osascript', '-e',
                 'display notification "NEVA self-test" with title "Self-test"'],
                capture_output=True, timeout=5
            )
            results['3_osascript'] = 'PASS (визуально проверьте уведомление)'
        except Exception as e:
            results['3_osascript'] = f'FAIL: {e}'

        # 4. atomic write/read
        try:
            test = DEFAULT_STATE.copy()
            test['state'] = 'SELF_TEST'
            self._write_state(test)
            loaded = json.load(open(STATE_PATH))
            assert loaded['state'] == 'SELF_TEST', "state не совпадает"
            self._write_state(DEFAULT_STATE.copy())
            results['4_atomic_write'] = 'PASS'
        except Exception as e:
            results['4_atomic_write'] = f'FAIL: {e}'

        # 5. Ollama serve
        try:
            urllib.request.urlopen('http://localhost:11434/api/tags', timeout=3)
            proc = self._find_ollama_process()
            results['5_ollama_serve'] = (
                'PASS' if proc
                else 'WARN: API отвечает, процесс не найден psutil'
            )
        except Exception as e:
            results['5_ollama_serve'] = f'FAIL: {e}'

        # 6. FSM
        try:
            all_states = set(FSM_TRANSITIONS.keys())
            for state, transitions in FSM_TRANSITIONS.items():
                for t in transitions:
                    assert t in all_states, f"{t} не является состоянием"
            results['6_fsm'] = f'PASS ({len(all_states)} состояний)'
        except AssertionError as e:
            results['6_fsm'] = f'FAIL: {e}'

        # 7. Конфигурация
        results['7_config'] = (
            'PASS' if self._validate_config(self.config)
            else 'FAIL: конфиг невалиден'
        )

        # 8. Corrupted recovery
        try:
            orig = open(STATE_PATH).read() if os.path.exists(STATE_PATH) else None
            with open(STATE_PATH, 'w') as f:
                f.write('{ bad json }}}')
            recovered = self._load_state()
            assert recovered['state'] == 'NOMINAL'
            if orig:
                with open(STATE_PATH, 'w') as f:
                    f.write(orig)
            else:
                os.unlink(STATE_PATH)
            results['8_corrupted_recovery'] = 'PASS'
        except Exception as e:
            results['8_corrupted_recovery'] = f'FAIL: {e}'

        # Вывод
        failed = []
        for name, result in results.items():
            if result.startswith('PASS'):
                icon = '✅'
            elif result.startswith('WARN'):
                icon = '⚠️'
            else:
                icon = '❌'
                failed.append(name)
            print(f"  {icon} {name}: {result}")

        print()
        if failed:
            print(f"❌ FAIL: {len(failed)} проверок не прошли: {failed}")
            sys.exit(1)
        else:
            print(f"✅ PASS: все {len(results)} проверок прошли")

    # ─── Главный цикл ────────────────────────────────────────────────────────
    def run(self):
        self.logger.info("=== NEVA Thermal Guard v9 запущен ===")
        if self.dry_run:
            self.logger.info("[DRY-RUN] режим активен")

        self._check_dirs()
        self.state = self._load_state()
        self.config = self._load_config()
        self._restore_cooldown()
        self._resolve_pending_on_start()

        self.logger.info(
            f"Старт: state={self.state['state']} "
            f"ollama_available={self.state['ollama_available']}"
        )

        while True:
            try:
                self._detect_sleep_wake()
                self._check_pending_timeout()

                # Disable flag
                if DISABLE_FLAG.exists():
                    if not self._disable_notified:
                        self.logger.warning("[WARNING] Guard DISABLED by flag file")
                        self._notify("[WARNING] Thermal Guard ОТКЛЮЧЁН файлом-семафором")
                        self._disable_notified = True
                    time.sleep(self.config.get('poll_nominal_sec', 30))
                    continue
                else:
                    self._disable_notified = False

                self._refresh_config()
                self._check_ollama_serve()

                if self.state['state'] == 'BLOCKED':
                    self._sync_state_with_reality()

                temp, is_stale = self._read_temp()
                mem = self._read_memory()

                self.last_temp = temp
                self.last_swap = mem['swap_gb']

                # Обновить метрики в state
                self.state['temp_c'] = temp
                self.state['swap_gb'] = mem['swap_gb']
                self.state['mem_pct'] = mem['mem_pct']
                self.state['memory_pressure_high'] = mem['memory_pressure_high']

                # Пропустить FSM при устаревших данных в чувствительных состояниях
                if is_stale and self.state['state'] in ('HOT_PENDING', 'WARM'):
                    self.logger.debug(
                        f"cycle temp=stale swap={mem['swap_gb']:.1f} "
                        f"mem={mem['mem_pct']:.0f}% state={self.state['state']}"
                    )
                    time.sleep(self.config.get('poll_active_sec', 10))
                    continue

                level = self._determine_level(temp, mem['swap_gb'], mem['mem_pct'])
                self._act(level)

                self.logger.debug(
                    f"cycle temp={temp} stale={is_stale} "
                    f"swap={mem['swap_gb']:.1f} mem={mem['mem_pct']:.0f}% "
                    f"state={self.state['state']} "
                    f"ollama={self.state['ollama_available']}"
                )

                # Интервал опроса по состоянию
                state = self.state['state']
                if state == 'HOT_PENDING':
                    interval = self.config.get('poll_pending_sec', 2)
                elif state == 'NOMINAL':
                    interval = self.config.get('poll_nominal_sec', 30)
                else:
                    interval = self.config.get('poll_active_sec', 10)

                time.sleep(interval)

            except KeyboardInterrupt:
                self.logger.info("Guard остановлен (KeyboardInterrupt)")
                break
            except Exception as e:
                self.logger.error(f"Ошибка цикла: {e}", exc_info=True)
                time.sleep(10)


# ─── Точка входа ─────────────────────────────────────────────────────────────
def main():
    dry_run = '--dry-run' in sys.argv
    self_test = '--self-test' in sys.argv

    guard = ThermalGuard(dry_run=dry_run)

    if self_test:
        guard.run_self_test()
        return

    guard.run()

if __name__ == '__main__':
    main()
