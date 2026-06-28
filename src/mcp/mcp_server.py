"""
mcp_server_v3.4.py — NEVA MCP Server
Версия: 3.4 | Дата: 2026-06-14

Изменения v3.3 → v3.4:
  FIX-20: Approval Gate зависание (hang 4 мин) — таймаут poll-loop
    - APPROVAL_HARD_TIMEOUT = 90с (вместо 120 итераций без выхода)
    - poll-loop выходит по deadline = time.time() + APPROVAL_HARD_TIMEOUT
    - при истечении → auto-cancel + немедленный ответ Клоду
    - уведомление Директору через osascript при timeout
    - логирование APPROVAL_TIMEOUT и APPROVAL_AUTO_CANCEL
  FIX-19: сохранено (_notify_director non-blocking)
"""

import sys
import json
import os
import secrets
import urllib.request
import urllib.error
import time as _time
import queue as _queue
import subprocess as _subprocess
import hashlib as _hashlib
import threading as _threading
import logging
from datetime import datetime, timezone


def _load_policy() -> dict:
    try:
        policy_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "neva_policy.json")
        with open(policy_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_POLICY     = _load_policy()
_MCP_POLICY = _POLICY.get("mcp_executor", {})

APPROVAL_URL          = _MCP_POLICY.get("approval_server_url", "http://127.0.0.1:8766")
APPROVAL_HARD_TIMEOUT = 90   # FIX-20: жёсткий потолок ожидания решения (90с)
PENDING_TTL_SECONDS   = 120  # время жизни записи в pending_confirmations
POLL_INTERVAL         = 0.5  # интервал опроса

_WRITE_OPS = set(_MCP_POLICY.get("audit_write_ops", [
    "file_write", "git_commit", "git_push", "file_delete", "file_move", "file_rename"
]))
_BASE_DIR = os.path.realpath(os.path.expanduser("~/Documents/NEVA_MCP_BRIDGE"))

_AUDIT_QUEUE: _queue.Queue = _queue.Queue(maxsize=_MCP_POLICY.get("audit_queue_maxsize", 100))
_audit_worker_started = False
_flagman_router = None


def _start_audit_worker():
    global _audit_worker_started, _flagman_router
    if _audit_worker_started:
        return
    try:
        from background_auditor import ExecutorAuditWorker, FlagmanRouter
        worker = ExecutorAuditWorker(_AUDIT_QUEUE)
        worker.start()
        _flagman_router = FlagmanRouter()
        _audit_worker_started = True
        logger.info("ExecutorAuditWorker started (v3.4)")
    except Exception as e:
        logger.warning(f"ExecutorAuditWorker start failed: {e}")


def _assess_risk(action: str, path: str = "", files: list = None) -> str:
    try:
        from background_auditor import assess_risk
        return assess_risk(action, path, files or [])
    except Exception:
        return "high"


def _notify_director(title: str, message: str, sound: bool = True):
    """FIX-19: non-blocking."""
    def _run():
        try:
            from background_auditor import notify_director
            notify_director(title, message, sound)
        except Exception as e:
            logger.warning(f"notify_director failed: {e}")
    _threading.Thread(target=_run, daemon=True).start()


def _notify_osascript(title: str, message: str, sound: str = "Basso"):
    """FIX-20: быстрое уведомление при timeout (non-blocking)."""
    def _run():
        try:
            _subprocess.run(
                ["osascript", "-e",
                 f'display notification "{message}" with title "{title}" sound name "{sound}"'],
                capture_output=True, timeout=5
            )
        except Exception:
            pass
    _threading.Thread(target=_run, daemon=True).start()


def _log_low_risk(action: str, risk: str, ai_verdict: str, status: str, path: str = ""):
    try:
        from background_auditor import log_low_risk_op
        log_low_risk_op(action, risk, ai_verdict, status, path)
    except Exception as e:
        logger.warning(f"log_low_risk failed: {e}")


def _compute_diff(action: str, path: str) -> tuple:
    diff_text, diff_lines, files_changed = "", 0, 0
    if action not in ("file_write", "git_commit"):
        return diff_text, diff_lines, files_changed
    try:
        cmd = ["git", "-C", _BASE_DIR, "diff", "HEAD"]
        if path:
            cmd += ["--", path]
        r = _subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        diff_text = r.stdout[:5000]
        diff_lines = len([l for l in diff_text.splitlines()
            if (l.startswith("+") or l.startswith("-"))
            and not l.startswith("+++") and not l.startswith("---")])
        files_changed = len([l for l in diff_text.splitlines() if l.startswith("diff --git")])
    except Exception:
        files_changed = 1
    return diff_text, diff_lines, files_changed


def _enqueue_audit(action: str, path: str, result: dict) -> bool:
    diff_text, diff_lines, files_changed = _compute_diff(action, path)
    op_hash = _hashlib.sha256(f"{action}:{path}:{_time.time()}".encode()).hexdigest()[:12]
    task = {
        "hash": op_hash, "intent": action, "diff": diff_text,
        "output": str(result)[:1000], "operation_type": action,
        "source": "claude_desktop", "double_review_passed": False,
        "diff_lines": diff_lines, "files_changed": files_changed,
    }
    try:
        _AUDIT_QUEUE.put_nowait(task)
        return True
    except _queue.Full:
        logger.warning(f"AUDIT_QUEUE_FULL action={action}")
        return action not in _WRITE_OPS


log_path = os.path.expanduser("~/Library/Logs/NEVA/mcp_server.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)
logging.basicConfig(filename=log_path, level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

print("NEVA MCP v3.4 starting", file=sys.stderr, flush=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_validator import validate
from mcp_executor import run

pending_confirmations: dict = {}


def _cleanup_expired():
    now = datetime.now(timezone.utc).timestamp()
    expired = [k for k, v in pending_confirmations.items()
               if now - v["ts"] > PENDING_TTL_SECONDS]
    for k in expired:
        del pending_confirmations[k]


def _build_confirmation_widget(action: str, payload: dict, token: str,
                               ai_opinion: str = "") -> str:
    if action == "git_commit":
        params     = payload.get("params", {})
        files      = params.get("files", [])
        message    = params.get("message", "")
        files_html = "".join(
            f'<div class="frow"><span class="fname">{f}</span></div>' for f in files
        )
        detail_html = f"""
        <div class="section-lbl">СООБЩЕНИЕ</div>
        <div class="msg-box">{message}</div>
        <div class="section-lbl">ФАЙЛЫ ({len(files)} шт)</div>
        <div class="files-block">{files_html}</div>"""
    elif action == "file_write":
        params      = payload.get("params", {})
        path        = params.get("path", "")
        content_len = len(params.get("content", ""))
        detail_html = f"""
        <div class="section-lbl">ФАЙЛ</div>
        <div class="msg-box">{path}</div>
        <div class="section-lbl">РАЗМЕР</div>
        <div class="msg-box">{content_len} байт</div>"""
    else:
        detail_html = f'<div class="msg-box">{action}</div>'

    ai_html = ""
    if ai_opinion:
        ai_html = f"""
        <div class="section-lbl">🤖 МНЕНИЕ AI</div>
        <div class="ai-box">{ai_opinion}</div>"""

    return f"""<style>
.cv-box{{background:var(--color-background-primary);border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-lg);padding:1.25rem 1.5rem;max-width:560px;margin:.5rem auto}}
.cv-hdr{{display:flex;align-items:center;gap:10px;margin-bottom:1rem;padding-bottom:.75rem;border-bottom:0.5px solid var(--color-border-tertiary)}}
.cv-badge{{background:var(--color-background-warning);color:var(--color-text-warning);font-size:11px;font-weight:500;padding:3px 10px;border-radius:var(--border-radius-md)}}
.cv-title{{font-size:15px;font-weight:500;color:var(--color-text-primary);margin:0}}
.section-lbl{{font-size:12px;color:var(--color-text-secondary);font-weight:500;margin:.75rem 0 .4rem;letter-spacing:.03em}}
.msg-box{{background:var(--color-background-secondary);border-radius:var(--border-radius-md);padding:8px 12px;font-size:13px;color:var(--color-text-primary);font-family:var(--font-mono)}}
.ai-box{{background:var(--color-background-secondary);border-left:3px solid #1a7f4b;border-radius:var(--border-radius-md);padding:8px 12px;font-size:13px;color:var(--color-text-primary);font-style:italic}}
.files-block{{border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-md);overflow:hidden}}
.frow{{display:flex;align-items:center;gap:8px;padding:6px 12px;font-size:13px;color:var(--color-text-primary);border-bottom:0.5px solid var(--color-border-tertiary)}}
.frow:last-child{{border-bottom:none}}
.fname{{font-family:var(--font-mono);flex:1}}
.btn-row{{display:flex;gap:10px;margin-top:1.25rem}}
.btn-ok{{flex:1;background:#1a7f4b;color:#fff;border:none;border-radius:var(--border-radius-md);padding:11px 0;font-size:15px;font-weight:500;cursor:pointer;transition:opacity .15s}}
.btn-ok:hover{{opacity:.88}}
.btn-no{{flex:1;background:#b91c1c;color:#fff;border:none;border-radius:var(--border-radius-md);padding:11px 0;font-size:15px;font-weight:500;cursor:pointer;transition:opacity .15s}}
.btn-no:hover{{opacity:.88}}
.token-info{{font-size:11px;color:var(--color-text-secondary);text-align:center;margin-top:.5rem}}
.timeout-bar{{height:3px;background:#fbbf24;border-radius:2px;margin-top:8px;animation:shrink {APPROVAL_HARD_TIMEOUT}s linear forwards}}
@keyframes shrink{{from{{width:100%}}to{{width:0%}}}}
</style>
<div class="cv-box">
<div class="cv-hdr"><span class="cv-badge">КРАСНАЯ ЗОНА: {action.upper()}</span>
<p class="cv-title">Требует подтверждения Директора</p></div>
{detail_html}{ai_html}
<div class="btn-row">
<button class="btn-ok" onclick="confirm_{token}()">✅ Подтвердить</button>
<button class="btn-no" onclick="cancel_{token}()">❌ Отклонить</button>
</div>
<div class="timeout-bar"></div>
<div class="token-info">Токен: {token} · auto-cancel через {APPROVAL_HARD_TIMEOUT}с</div>
</div>
<script>
function confirm_{token}(){{
  document.querySelector('.btn-row').style.opacity='0.4';
  document.querySelector('.btn-row').style.pointerEvents='none';
  sendPrompt('CONFIRM:{token}');
}}
function cancel_{token}(){{
  document.querySelector('.btn-row').style.opacity='0.4';
  document.querySelector('.btn-row').style.pointerEvents='none';
  sendPrompt('CANCEL:{token}');
}}
</script>"""


def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()



def _handle_memory_search(rid, args):
    """Поиск в памяти NEVA v3 для Claude Desktop."""
    query = args.get("query", "").strip()
    if not query:
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"content": [{"type": "text",
                  "text": '{"error": "query обязателен"}'}]}})
        return
    include_obsolete = args.get("include_obsolete", False)
    try:
        import sys as _sys2
        neva_path = os.path.expanduser("~/Documents/NEVA")
        if neva_path not in _sys2.path:
            _sys2.path.insert(0, neva_path)
        from src.memory.db import init_db
        from src.memory.search import search as mem_search
        init_db()
        result = mem_search(query=query, asked_by="claude_desktop",
                            include_obsolete=include_obsolete)
        text = result.get("context_package", "Информация не найдена.")
        meta = (f"[Память NEVA: уровень {result.get('level_found')}, "
                f"найдено {result.get('results_count',0)} записей, "
                f"{result.get('duration_ms')}мс]")
        output = f"{text}\n\n---\n{meta}"
    except Exception as e:
        logger.error(f"memory_search error: {e}", exc_info=True)
        output = f"Ошибка поиска в памяти NEVA: {e}"
    send({"jsonrpc": "2.0", "id": rid,
          "result": {"content": [{"type": "text", "text": output}]}})


def handle_tool_call(rid, params):
    tool_name  = params.get("name", "neva_execute")
    args       = params.get("arguments", {})
    if tool_name == "memory_search":
        _handle_memory_search(rid, args)
        return
    raw        = json.dumps(args)
    action_str = args.get("action", "")

    if action_str.startswith("CONFIRM:") or action_str.startswith("CANCEL:"):
        token = action_str.split(":", 1)[1].strip()
        _cleanup_expired()
        if action_str.startswith("CANCEL:"):
            pending_confirmations.pop(token, None)
            result = {"status": "cancelled", "reason": "Директор отклонил операцию"}
            logger.info(f"CANCEL token={token}")
        else:
            pending = pending_confirmations.pop(token, None)
            if not pending:
                result = {"status": "error", "reason": "TOKEN_EXPIRED_OR_UNKNOWN"}
            else:
                pending["data"]["_server_confirmed"] = True
                result = run(pending)
                logger.info(f"CONFIRMED token={token} action={pending['data'].get('action')}")
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"content": [{"type": "text",
                  "text": json.dumps(result, ensure_ascii=False, indent=2)}]}})
        return

    validated = validate(raw)
    logger.info(f"tools/call action={action_str} validated={validated.get('ok')}")
    _path  = validated.get("data", {}).get("params", {}).get("path", "")
    _files = validated.get("data", {}).get("params", {}).get("files", [])

    risk = _assess_risk(action_str, _path, _files)
    logger.info(f"risk={risk} action={action_str} path={_path}")

    if risk == "none":
        result = run(validated)
        _enqueue_audit(action_str, _path, result)
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"content": [{"type": "text",
                  "text": json.dumps(result, ensure_ascii=False, indent=2)}]}})
        return

    if risk == "low":
        ai_result = {"auto_approve": False, "verdict": "ALERT", "summary": "reviewer unavailable"}
        if _flagman_router:
            diff_text, diff_lines, _ = _compute_diff(action_str, _path)
            ai_result = _flagman_router.review_low_risk({
                "intent": action_str, "diff": diff_text, "path": _path,
                "files": _files, "operation_type": action_str, "diff_lines": diff_lines,
            })
        if ai_result.get("auto_approve"):
            validated["data"]["_server_confirmed"] = True
            result = run(validated)
            _log_low_risk(action_str, risk,
                f"APPROVE conf={ai_result.get('confidence',0):.2f}",
                "auto_approved", _path)
            logger.info(f"LOW_RISK AUTO_APPROVED: {action_str}")
            _enqueue_audit(action_str, _path, result)
            send({"jsonrpc": "2.0", "id": rid,
                  "result": {"content": [{"type": "text",
                      "text": json.dumps(result, ensure_ascii=False, indent=2)}]}})
        else:
            _log_low_risk(action_str, risk,
                f"ALERT conf={ai_result.get('confidence',0):.2f}",
                "sent_to_director", _path)
            _notify_director("NEVA — LOW RISK", f"{action_str}: AI не уверен, нужен клик")
            _send_for_confirmation(rid, validated, action_str, _path,
                ai_opinion=ai_result.get("summary", ""))
        return

    # high
    _notify_director("🚨 NEVA — КРАСНАЯ ЗОНА",
        f"{action_str}: подтверждение Директора", sound=True)
    ai_opinion = ""
    if _flagman_router:
        try:
            diff_text, _, _ = _compute_diff(action_str, _path)
            rev = _flagman_router.review_low_risk({
                "intent": action_str, "diff": diff_text,
                "path": _path, "files": _files, "operation_type": action_str,
            })
            ai_opinion = rev.get("summary", "")
        except Exception:
            pass
    _send_for_confirmation(rid, validated, action_str, _path, ai_opinion=ai_opinion)


def _send_for_confirmation(rid, validated, action: str, path: str, ai_opinion: str = ""):
    """
    FIX-20: жёႉткий deadline на poll-loop.
    При истечении APPROVAL_HARD_TIMEOUT → auto-cancel, немедленный ответ Клоду.
    """
    token = secrets.token_hex(8)
    _cleanup_expired()
    pending_confirmations[token] = {
        "data": validated,
        "ts":   datetime.now(timezone.utc).timestamp()
    }
    logger.info(f"PENDING token={token} action={action} hard_timeout={APPROVAL_HARD_TIMEOUT}s")

    # Отправка в Approval Gate
    approval_ok = False
    try:
        payload_bytes = json.dumps({
            "token":  token, "action": action,
            "params": validated.get("data", {}).get("params", {}),
            "ts":     datetime.now(timezone.utc).timestamp()
        }, ensure_ascii=False).encode()
        req = urllib.request.Request(f"{APPROVAL_URL}/pending",
            data=payload_bytes, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=5)
        approval_ok = True
        logger.info(f"APPROVAL_SENT token={token}")
    except Exception as e:
        logger.warning(f"Approval server недоступен: {e}")

    if not approval_ok:
        pending_confirmations.pop(token, None)
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"content": [{"type": "text", "text": (
                  f"⚠️ NEVA Approval Gate недоступен.\nТокен: {token}"
              )}]}})
        return

    # Отправляем widget Клоду сразу (non-blocking)
    send({"jsonrpc": "2.0", "id": rid,
          "result": {"content": [{"type": "text", "text": (
              f"⏳ Операция '{action}' отправлена на подтверждение.\n"
              f"Откройте: http://127.0.0.1:8765\nТокен: {token}"
          )}]}})

    # FIX-20: poll-loop с deadline
    deadline = _time.time() + APPROVAL_HARD_TIMEOUT
    decision = None
    poll_count = 0

    while _time.time() < deadline:
        _time.sleep(POLL_INTERVAL)
        poll_count += 1
        remaining = deadline - _time.time()

        # Логируем каждые 30с
        if poll_count % 60 == 0:
            logger.info(f"POLL token={token} remaining={remaining:.0f}s")

        try:
            req = urllib.request.Request(f"{APPROVAL_URL}/poll",
                data=json.dumps({"token": token}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            resp = urllib.request.urlopen(req, timeout=3)
            data = json.loads(resp.read())
            decision = data.get("decision")
            if decision:
                break
        except Exception:
            pass

    # FIX-20: обработка результата
    if decision == "confirm":
        pending = pending_confirmations.pop(token, None)
        if pending:
            pending["data"]["_server_confirmed"] = True
            final_result = run(pending)
            logger.info(f"CONFIRMED token={token} polls={poll_count}")
            _enqueue_audit(action, path, final_result)
            # Ответ через новый tool call (придёт серез CONFIRM:token)
            send({"jsonrpc": "2.0", "id": rid,
                  "result": {"content": [{"type": "text",
                      "text": json.dumps(final_result, ensure_ascii=False, indent=2)}]}})
        else:
            send({"jsonrpc": "2.0", "id": rid,
                  "result": {"content": [{"type": "text",
                      "text": '{"status": "error", "reason": "TOKEN_EXPIRED"}'}]}})

    elif decision in ("cancel", "cancelled"):
        pending_confirmations.pop(token, None)
        logger.info(f"CANCELLED token={token} polls={poll_count}")
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"content": [{"type": "text",
                  "text": '{"status": "cancelled", "reason": "Директор отклонил операцию"}'}]}})

    else:
        # FIX-20: AUTO-CANCEL по таймауту
        pending_confirmations.pop(token, None)
        logger.warning(
            f"APPROVAL_TIMEOUT token={token} action={action} "
            f"polls={poll_count} timeout={APPROVAL_HARD_TIMEOUT}s — AUTO-CANCEL"
        )
        _notify_osascript(
            "⏱ NEVA — Timeout",
            f"{action}: подтверждение не получено за {APPROVAL_HARD_TIMEOUT}с — отменено"
        )
        send({"jsonrpc": "2.0", "id": rid,
              "result": {"content": [{"type": "text", "text": json.dumps({
                  "status":  "timeout",
                  "reason":  f"Подтверждение не получено за {APPROVAL_HARD_TIMEOUT}с — авто-отмена",
                  "token":   token,
                  "action":  action,
                  "hint":    "Повторите операцию и подтвердите в течение 90с",
              }, ensure_ascii=False, indent=2)}]}})


def main():
    logger.info("NEVA MCP Server v3.4 started (FIX-20: approval timeout)")
    _start_audit_worker()
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try:
            req = json.loads(line)
        except Exception:
            send({"jsonrpc": "2.0", "id": None,
                  "error": {"code": -32700, "message": "Parse error"}})
            continue
        rid    = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})
        logger.info(f"{method} id={rid}")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "neva_executor", "version": "3.4"},
                "capabilities": {"tools": {}}
            }})
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": rid, "result": {"tools": [{
                "name": "neva_execute",
                "description": (
                    "NEVA MCP Executor v3.4. "
                    "Actions: git_status, file_tree, file_read, file_write, "
                    "system_info, run_tests, diagnostics, ollama_list, git_commit, neva_status. "
                    "neva_status params: level=summary|full. "
                    "git_push ЗАБЛОКИРОВАН. "
                    "Approval: auto-cancel через 90с если нет ответа."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "params": {"type": "object", "additionalProperties": True}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "memory_search",
                "description": (
                    "Поиск в памяти NEVA v3. "
                    "Вызывать когда в контексте нет нужных данных: решения Директора, "
                    "архитектура, задачи, аудиты, история чатов. "
                    "Возвращает сжатый context_package до 500 слов."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Поисковый запрос на русском, 3-10 слов"
                        },
                        "include_obsolete": {
                            "type": "boolean",
                            "default": False
                        }
                    },
                    "required": ["query"]
                }
            }
        ]}})
        elif method == "tools/call":
            handle_tool_call(rid, params)
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": rid, "result": {}})
        else:
            send({"jsonrpc": "2.0", "id": rid,
                  "error": {"code": -32601, "message": f"Method not found: {method}"}})


if __name__ == "__main__":
    main()
