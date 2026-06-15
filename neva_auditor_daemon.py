#!/usr/bin/env python3
"""
neva_auditor_daemon.py — NEVA Auditor Daemon (Архитектура Т6)
Версия: 1.0 | Дата: 2026-06-15 | Архитектор: Claude | Директор: Серж
"""
import os, sys, json, time, queue, signal, socket, logging, threading
from pathlib import Path

BASE_DIR  = Path(os.path.expanduser("~/Documents/NEVA_MCP_BRIDGE"))
SOCK_PATH = BASE_DIR / "auditor.sock"
LOG_PATH  = BASE_DIR / "logs" / "auditor.log"
PIDFILE   = BASE_DIR / "logs" / "auditor_daemon.pid"
sys.path.insert(0, str(BASE_DIR))

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=str(LOG_PATH), level=logging.INFO,
    format="%(asctime)s [auditor] %(levelname)s %(message)s")
log = logging.getLogger("auditor_daemon")

SELF_TEST_RESULTS = {}

def run_self_test():
    passed = 0
    total  = 5
    try:
        from background_auditor import ExecutorAuditWorker, FlagmanRouter, assess_risk
        SELF_TEST_RESULTS['import'] = 'PASS'; passed += 1
    except Exception as e:
        SELF_TEST_RESULTS['import'] = f'FAIL: {e}'
        log.error(f"ST-01 FAIL: {e}"); return False
    try:
        from background_auditor import assess_risk, RISK_NONE, RISK_LOW, RISK_HIGH
        ok = (assess_risk("file_read") == RISK_NONE and
              assess_risk("file_write", "test.py") == RISK_LOW and
              assess_risk("file_write", "governance/x.md") == RISK_HIGH)
        SELF_TEST_RESULTS['assess_risk'] = 'PASS' if ok else 'FAIL'
        if ok: passed += 1
        else: log.error("ST-02 FAIL")
    except Exception as e:
        SELF_TEST_RESULTS['assess_risk'] = f'FAIL: {e}'
    try:
        queue.Queue(maxsize=10)
        SELF_TEST_RESULTS['queue'] = 'PASS'; passed += 1
    except Exception as e:
        SELF_TEST_RESULTS['queue'] = f'FAIL: {e}'
    try:
        test_sock = str(BASE_DIR / "logs" / "_test.sock")
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(test_sock); s.close(); os.unlink(test_sock)
        SELF_TEST_RESULTS['socket'] = 'PASS'; passed += 1
    except Exception as e:
        SELF_TEST_RESULTS['socket'] = f'FAIL: {e}'
    try:
        log.info("ST-05: self-test log write OK")
        SELF_TEST_RESULTS['log_write'] = 'PASS'; passed += 1
    except Exception as e:
        SELF_TEST_RESULTS['log_write'] = f'FAIL: {e}'
    log.info(f"Self-test: {passed}/{total} PASS")
    return passed == total

class AuditorDaemon:
    def __init__(self):
        self._audit_queue = queue.Queue(maxsize=200)
        self._worker      = None
        self._server_sock = None
        self._running     = False

    def _start_worker(self):
        from background_auditor import ExecutorAuditWorker
        self._worker = ExecutorAuditWorker(self._audit_queue)
        self._worker.start()
        log.info("ExecutorAuditWorker started")

    def _handle_client(self, conn):
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk: break
                data += chunk
                if len(data) > 1_000_000: break
            if data:
                task = json.loads(data.decode("utf-8"))
                try:
                    self._audit_queue.put_nowait(task)
                    conn.sendall(b'{"status":"queued"}\n')
                except queue.Full:
                    conn.sendall(b'{"status":"queue_full"}\n')
                    log.warning("Audit queue full")
        except Exception as e:
            log.error(f"Client handler: {e}")
        finally:
            try: conn.close()
            except: pass

    def _accept_loop(self):
        while self._running:
            try:
                conn, _ = self._server_sock.accept()
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except OSError:
                if self._running: log.error("Accept loop OSError")
                break
            except Exception as e:
                log.error(f"Accept: {e}"); time.sleep(1)

    def _heartbeat_loop(self):
        while self._running:
            time.sleep(60)
            if self._running:
                w = self._worker
                log.info(f"heartbeat: queue={self._audit_queue.qsize()} worker={'alive' if w and w.is_alive() else 'DEAD'}")
                if not (w and w.is_alive()):
                    log.warning("Worker мёртв — перезапускаю")
                    try: self._start_worker()
                    except Exception as e: log.error(f"Worker restart: {e}")

    def start(self):
        self._running = True
        self._start_worker()
        if SOCK_PATH.exists(): SOCK_PATH.unlink()
        self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(str(SOCK_PATH))
        self._server_sock.listen(32)
        PIDFILE.write_text(str(os.getpid()))
        threading.Thread(target=self._accept_loop,   daemon=True, name="AcceptLoop").start()
        threading.Thread(target=self._heartbeat_loop, daemon=True, name="Heartbeat").start()
        log.info(f"neva_auditor_daemon v1.0 started (pid={os.getpid()}) sock={SOCK_PATH}")

    def stop(self):
        log.info("Stopping")
        self._running = False
        try: self._server_sock.close()
        except: pass
        for p in (SOCK_PATH, PIDFILE):
            try: p.unlink()
            except: pass
        log.info("Stopped")

    def run_forever(self):
        self.start()
        try:
            while self._running: time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self.stop()

_daemon_instance = None

def _handle_sigterm(sig, frame):
    log.info("SIGTERM")
    if _daemon_instance: _daemon_instance.stop()
    sys.exit(0)

def _handle_sigusr1(sig, frame):
    if _daemon_instance:
        d = _daemon_instance
        log.info(f"SIGUSR1: queue={d._audit_queue.qsize()} worker={'alive' if d._worker and d._worker.is_alive() else 'DEAD'}")

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        print("neva_auditor_daemon.py v1.0 self-test:")
        ok = run_self_test()
        for k, v in SELF_TEST_RESULTS.items():
            print(f"  {'✅' if 'PASS' in str(v) else '❌'} {k}: {v}")
        passed = sum(1 for v in SELF_TEST_RESULTS.values() if 'PASS' in str(v))
        print(f"\n{passed}/{len(SELF_TEST_RESULTS)} PASS")
        sys.exit(0 if ok else 1)
    if "--diag" in sys.argv:
        print(f"PID файл: {PIDFILE}")
        if PIDFILE.exists():
            pid = PIDFILE.read_text().strip()
            try: os.kill(int(pid), 0); print(f"Процесс {pid} — ЖИВОЙ")
            except: print(f"Процесс {pid} — МЁРТВ")
        else: print("PID файл нет — daemon не запущен")
        print(f"Socket: {'есть' if SOCK_PATH.exists() else 'НЕТ'}")
        import subprocess
        r = subprocess.run(["tail", "-5", str(LOG_PATH)], capture_output=True, text=True)
        print(f"Лог:\n{r.stdout}")
        sys.exit(0)
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGUSR1, _handle_sigusr1)
    if not run_self_test():
        log.error("Self-test провален — не запускаюсь")
        sys.exit(1)
    _daemon_instance = AuditorDaemon()
    _daemon_instance.run_forever()
