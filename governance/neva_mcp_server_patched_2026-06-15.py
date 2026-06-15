#!/usr/bin/env python3
"""
neva_mcp_server.py v2.0
Streamable HTTP transport (MCP spec 2025-11-25)
Один POST /mcp endpoint для JSON-RPC.
Порт 9000 — MCP Streamable HTTP для Claude Desktop
Порт 9001 — Live Dashboard для Brave
Живёт независимо от Claude Desktop через launchd KeepAlive.
"""
import json, logging, os, subprocess, sys, threading, time, socket
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE   = Path('~/Documents/NEVA_MCP_BRIDGE').expanduser()
NEVA   = Path('~/Documents/NEVA').expanduser()
LOGS   = BASE / 'logs'
STATE  = BASE / 'state'
ESCALATIONS = BASE / 'escalations'
MCP_PORT  = 9000
DASH_PORT = 9001

LOGS.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [mcp-server] %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(LOGS / 'mcp_server_net.log'),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger('neva_mcp_server')

sys.path.insert(0, str(BASE))
from neva_mcp_events import push_event, get_events, set_claude_reply, pop_claude_reply, peek_claude_reply
from neva_mcp_patch  import apply_patch

_approval_store: dict = {}
_approval_lock  = threading.Lock()


def _load_token() -> str:
    try:
        for line in (NEVA / '.env').read_text().splitlines():
            if line.startswith('NEVA_ADMIN_TOKEN='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception: pass
    return os.environ.get('NEVA_ADMIN_TOKEN', '')

ADMIN_TOKEN = _load_token()

# FIX: явно ставим BASE первым чтобы не загрузить tools/mcp_executor
import sys as _sys
if str(BASE) not in _sys.path:
    _sys.path.insert(0, str(BASE))
try:
    from mcp_executor import run as _executor_run
    from mcp_validator import validate as _executor_validate
    _EXECUTOR_OK = True
except ImportError as _e:
    _EXECUTOR_OK = False
    import logging as _l; _l.getLogger('neva_mcp_server').error(f'EXECUTOR IMPORT FAILED: {_e}')


# ─── ACTIONS ─────────────────────────────────────────────────────────────────

def _execute_action(action: str, params: dict) -> dict:
    if action == 'file_patch':
        path = params.get('path', ''); diff = params.get('diff', '')
        if not path or not diff: return {'status': 'error', 'reason': 'Нужны path и diff'}
        return apply_patch(path, diff)

    if action == 'file_append':
        path = params.get('path', '')
        try:
            with open((BASE / path).expanduser(), 'a', encoding='utf-8') as f:
                f.write(params.get('content', ''))
            return {'status': 'ok'}
        except Exception as e: return {'status': 'error', 'reason': str(e)}

    if action == 'file_lines':
        path = params.get('path', ''); start = params.get('start', 1); end = params.get('end', -1)
        try:
            lines = (BASE / path).expanduser().read_text(errors='replace').splitlines()
            return {'status': 'ok', 'lines': lines[start-1: end if end > 0 else None], 'total': len(lines)}
        except Exception as e: return {'status': 'error', 'reason': str(e)}

    if action == 'neva_status':  return _get_neva_status()

    if action == 'neva_heal':
        try:
            r = subprocess.run([sys.executable, str(BASE/'neva_medic.py'), '--heal'],
                               capture_output=True, text=True, timeout=90, cwd=str(BASE))
            return {'status': 'ok', 'output': r.stdout[:3000], 'rc': r.returncode}
        except Exception as e: return {'status': 'error', 'reason': str(e)}

    if action == 'neva_chronic':
        try: return {'status': 'ok', 'report': json.loads((STATE/'chronic_report.json').read_text())}
        except Exception as e: return {'status': 'error', 'reason': str(e)}

    if action == 'medic_events':
        return {'status': 'ok', 'events': get_events(params.get('n', 20))}

    if action == 'claude_reply':
        instruction = params.get('instruction', '')
        if not instruction: return {'status': 'error', 'reason': 'Нужна instruction'}
        set_claude_reply(instruction)
        push_event({'type': 'claude_reply', 'instruction': instruction[:200]})
        return {'status': 'ok', 'instruction': instruction}

    if action == 'approval_request':
        token = params.get('token', '')
        with _approval_lock: _approval_store[token] = {'payload': params, 'decision': None, 'ts': time.time()}
        return {'status': 'ok', 'token': token}

    if action == 'approval_poll':
        token = params.get('token', '')
        rec = _approval_store.get(token)
        return {'status': 'ok', 'decision': rec.get('decision') if rec else None} if rec \
            else {'status': 'error', 'reason': 'TOKEN_UNKNOWN'}

    if _EXECUTOR_OK:
        try:
            validated = _executor_validate(json.dumps({'action': action, 'params': params}))
            validated['data']['_server_confirmed'] = True
            return _executor_run(validated)
        except Exception as e: return {'status': 'error', 'reason': f'executor: {e}'}

    return {'status': 'error', 'reason': f'Неизвестное action: {action}'}


def _get_neva_status() -> dict:
    s = {'ts': datetime.now().isoformat()}
    try: s['medic_report'] = json.loads((STATE/'medic_report.json').read_text())
    except: s['medic_report'] = {}
    try:
        idx = json.loads((ESCALATIONS/'index.json').read_text())
        s['open_escalations'] = [e for e in idx if e.get('status') == 'OPEN']
    except: s['open_escalations'] = []
    try: s['chronic'] = json.loads((STATE/'chronic_report.json').read_text())
    except: s['chronic'] = {}
    s['medic_events'] = get_events(20)
    reply = peek_claude_reply()
    s['claude_reply_pending'] = reply if reply and not reply.get('read') else None
    try:
        ps = subprocess.run(['ps','aux'], capture_output=True, text=True).stdout
        s['processes'] = {
            'medic':    'neva_medic.py' in ps,
            'cc':       'neva_control_center' in ps,
            'agent':    'neva_repair_agent' in ps,
            'approval': 'neva_approval_server' in ps,
        }
    except: s['processes'] = {}
    return {'status': 'ok', 'neva': s}


# ─── JSON-RPC ─────────────────────────────────────────────────────────────────

TOOL_DEF = {
    'name': 'neva_execute',
    'description': (
        'NEVA MCP Server v2.0 (Streamable HTTP). '
        'Actions: git_status, file_tree, file_read, file_write, '
        'file_patch, file_append, file_lines, '
        'system_info, run_tests, git_commit, '
        'neva_status, neva_heal, neva_chronic, '
        'medic_events, claude_reply, '
        'approval_request, approval_poll'
    ),
    'inputSchema': {
        'type': 'object',
        'properties': {
            'action': {'type': 'string', 'description': 'Action name'},
            'params': {'type': 'object', 'additionalProperties': True,
                       'description': 'Action parameters'},
        },
        'required': ['action'],
    },
}


def _handle_jsonrpc(req: dict) -> dict:
    rid    = req.get('id')
    method = req.get('method', '')
    params = req.get('params', {})
    log.info(f'JSON-RPC {method} id={rid}')

    if method == 'initialize':
        return {'jsonrpc': '2.0', 'id': rid, 'result': {
            'protocolVersion': '2024-11-05',
            'serverInfo': {'name': 'neva_mcp_server', 'version': '2.0'},
            'capabilities': {'tools': {}},
        }}

    if method == 'tools/list':
        return {'jsonrpc': '2.0', 'id': rid, 'result': {'tools': [TOOL_DEF]}}

    if method == 'tools/call':
        args   = params.get('arguments', {})
        action = args.get('action', '')
        result = _execute_action(action, args.get('params', {}))
        return {'jsonrpc': '2.0', 'id': rid, 'result': {
            'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False, indent=2)}]
        }}

    if method in ('notifications/initialized', 'ping', 'notifications/cancelled'):
        return {'jsonrpc': '2.0', 'id': rid, 'result': {}}

    return {'jsonrpc': '2.0', 'id': rid,
            'error': {'code': -32601, 'message': f'Method not found: {method}'}}


# ─── STREAMABLE HTTP MCP HANDLER ─────────────────────────────────────────────────────

class MCPHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.debug(f'HTTP {self.command} {self.path} {fmt % args}')

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers',
                         'Content-Type, Authorization, MCP-Protocol-Version, MCP-Session-Id')
        self.send_header('Access-Control-Expose-Headers', 'MCP-Session-Id')

    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path).path

        # Health check
        if p == '/health':
            self._send_json({'status': 'ok', 'version': '2.0',
                             'transport': 'streamable-http', 'port': MCP_PORT})
            return

        # Medic читает ответ Claude
        if p == '/claude_reply':
            reply = pop_claude_reply()
            self._send_json({'instruction': reply['instruction'] if reply else None})
            return

        # Streamable HTTP GET — для опционального SSE streaming
        # Claude Desktop использует POST, но некоторые клиенты используют GET
        if p == '/mcp':
            session_id = self.headers.get('MCP-Session-Id', '')
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self._cors()
            self.end_headers()
            try:
                while True:
                    time.sleep(15)
                    self.wfile.write(b': ping\n\n')
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        self._send_json({'error': 'Not Found'}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        n = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(n) if n else b'{}'

        # Внутренние endpointы
        if p == '/events':
            try: push_event(json.loads(body))
            except Exception: pass
            self._send_json({'status': 'ok'})
            return

        if p == '/approval/respond':
            try:
                data = json.loads(body)
                tok = data.get('token', '')
                with _approval_lock:
                    if tok in _approval_store:
                        _approval_store[tok]['decision'] = data.get('decision', '')
                self._send_json({'status': 'ok', 'token': tok})
            except Exception as e:
                self._send_json({'error': str(e)}, 400)
            return

        # Главный Streamable HTTP endpoint
        if p == '/mcp':
            try:
                data = json.loads(body)
            except Exception:
                self._send_json({'error': 'Invalid JSON'}, 400)
                return

            # Один запрос — отвечаем JSON
            if isinstance(data, dict):
                resp = _handle_jsonrpc(data)
                # Если клиент принимает SSE — возвращаем event stream
                accept = self.headers.get('Accept', '')
                if 'text/event-stream' in accept:
                    out = json.dumps(resp, ensure_ascii=False)
                    body_out = f'data: {out}\n\n'.encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self._cors()
                    self.end_headers()
                    self.wfile.write(body_out)
                else:
                    self._send_json(resp)

            # Пакет запросов (batch) — отвечаем массивом
            elif isinstance(data, list):
                responses = [_handle_jsonrpc(r) for r in data if isinstance(r, dict)]
                accept = self.headers.get('Accept', '')
                if 'text/event-stream' in accept:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self._cors()
                    self.end_headers()
                    for r in responses:
                        out = f'data: {json.dumps(r, ensure_ascii=False)}\n\n'.encode()
                        self.wfile.write(out)
                else:
                    self._send_json(responses)
            else:
                self._send_json({'error': 'Invalid request'}, 400)
            return

        self._send_json({'error': 'Not Found'}, 404)

    def do_DELETE(self):
        # Session termination (Streamable HTTP spec)
        p = urlparse(self.path).path
        if p == '/mcp':
            self.send_response(200)
            self._cors()
            self.end_headers()
            return
        self._send_json({'error': 'Not Found'}, 404)


# ─── LIVE DASHBOARD (PORT 9001) ────────────────────────────────────────────────────

COMPONENT_MAP = [
    ('thermal_log_stale',     'Thermal Guard',     'thermal'),
    ('mcp_not_running',       'MCP Server',        'executor'),
    ('approval_not_running',  'Approval Server',   'executor'),
    ('approval_http_fail',    'Approval HTTP',     'executor'),
    ('sync_needed',           'AppSupport sync',   'deploy'),
    ('ollama_not_responding', 'Ollama',            'ollama'),
    ('ai_providers_all_down', 'AI провайдеры',   'ai'),
    ('auditor_log_stale',     'Auditor log',       'auditor'),
    ('executor_log_spam',     'executor spam',     'executor'),
    ('pending_unanswered',    'pending decisions', 'medic'),
    ('backoff',               'Backoff OK',        'medic'),
]


def _get_component_status() -> dict:
    components = {pid: {'name': name, 'status': 'ok'}
                  for pid, name, _ in COMPONENT_MAP}
    try:
        report   = json.loads((STATE/'medic_report.json').read_text())
        problems = {p['id'] for p in report.get('problems', [])}
        actions  = {a['problem_id']: a for a in report.get('actions', [])}
        for pid in components:
            if pid in problems:
                a = actions.get(pid, {})
                components[pid]['status'] = (
                    'backoff' if a.get('mode') == 'BACKOFF'
                    else 'fail' if not a.get('success', True)
                    else 'warn'
                )
    except: pass
    active = set()
    for ev in reversed(get_events(50)):
        t = ev.get('type', '')
        pid = ev.get('problem_id', '')
        if t in ('playbook_start', 'playbook_step') and pid: active.add(pid)
        elif t == 'playbook_end': active.discard(pid)
    for pid in active:
        if pid in components: components[pid]['status'] = 'active'
    return components


def _build_dashboard_html() -> str:
    components = _get_component_status()
    events     = get_events(30)
    reply      = peek_claude_reply()
    ICONS  = {'ok':'🟢','warn':'🟡','fail':'🔴','active':'🟡','backoff':'⏳'}
    COLORS = {'ok':'#4ade80','warn':'#fbbf24','fail':'#f87171','active':'#fbbf24','backoff':'#94a3b8'}
    cards = ''.join(
        f'<div style="background:#1a1f2e;border:1px solid {COLORS.get(i["status"],"#334155")}44;'
        f'border-radius:10px;padding:10px 14px">{ICONS.get(i["status"],chr(9899))} '
        f'<span style="font-size:12px;font-weight:600;color:{COLORS.get(i["status"],"#64748b")}">{i["name"]}</span></div>'
        for i in components.values()
    )
    EV_ICONS = {'heal_start':'🔄','problem_found':'⚠️','playbook_start':'▶',
                'playbook_step':'├','playbook_end':'✔','escalation':'🆘',
                'l2_start':'🤖','l2_end':'✔🤖','claude_reply':'💬'}
    ev_html = ''.join(
        f'<div style="font-size:11px;color:#94a3b8;padding:2px 0;font-family:monospace">'
        f'{ev.get("ts","")[-8:]} {EV_ICONS.get(ev.get("type",""),chr(8226))} '
        f'{ev.get("playbook","") or ev.get("problem_id","") or ev.get("type","")}'
        f'{(" → "+ev["step"]) if ev.get("step") else ""}'
        f'{(" "+ev["result"]) if ev.get("result") else ""}</div>'
        for ev in reversed(events[-15:])
    ) or '<div style="color:#475569;font-size:11px">ждём событий...</div>'
    reply_html = ''
    if reply and not reply.get('read'):
        reply_html = (f'<div style="background:#1e1035;border:1px solid #7c3aed;border-radius:8px;'
                      f'padding:10px;margin-top:8px">'
                      f'<div style="font-size:11px;color:#c4b5fd">💬 Ответ Claude ({reply["ts"][-8:]})</div>'
                      f'<div style="font-size:12px;color:#e2e8f0">{reply["instruction"]}</div></div>')
    try:
        actions = json.loads((STATE/'medic_report.json').read_text()).get('actions', [])
        hist = ''.join(
            f'<div style="font-size:11px;color:{"#4ade80" if a.get("success") else "#f87171"};padding:2px 0">'
            f'{"✅" if a.get("success") else "❌"} {a.get("mode","")} '
            f'{a.get("problem_id","")} → {a.get("playbook","")}</div>'
            for a in reversed(actions[-10:])
        )
    except: hist = '<div style="color:#475569;font-size:11px">нет данных</div>'
    now = datetime.now().strftime('%H:%M:%S')
    return f"""<!DOCTYPE html><html lang="ru"><head>
<meta charset="UTF-8"><meta http-equiv="refresh" content="3">
<title>NEVA Live</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,sans-serif;background:#0f1117;color:#e2e8f0;padding:16px}}
.hdr{{display:flex;align-items:center;gap:10px;margin-bottom:14px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.card{{background:#1a1f2e;border:1px solid #2d3748;border-radius:12px;padding:14px}}
.ct{{font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;margin-bottom:8px}}
</style></head><body>
<div class="hdr"><span style="font-size:22px">🔷</span>
<span style="font-size:17px;font-weight:700">NEVA Live Dashboard v2.0</span>
<span style="margin-left:auto;color:#475569;font-size:11px">{now} · Streamable HTTP</span></div>
<div class="grid">{cards}</div>
<div class="cols">
<div class="card"><div class="ct">💊 Medic — активность</div>
<div style="max-height:200px;overflow-y:auto">{ev_html}</div>{reply_html}</div>
<div class="card"><div class="ct">📊 История</div>
<div style="max-height:200px;overflow-y:auto">{hist}</div></div></div>
<div style="text-align:center;margin-top:10px">
<a href="http://localhost:8767" style="color:#60a5fa;font-size:12px">→ CC (8767)</a></div>
<div style="text-align:center;color:#334155;font-size:11px;margin-top:6px">NEVA Live · 3с · :9001</div>
</body></html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def do_GET(self):
        p = urlparse(self.path).path
        if p in ('/', '/dashboard'):
            body = _build_dashboard_html().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if p == '/api/status':
            body = json.dumps(_get_neva_status(), ensure_ascii=False, default=str).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        self.send_response(404); self.end_headers()


# ─── SELF TEST ─────────────────────────────────────────────────────────────────

def self_test() -> list:
    results = []
    for port in (MCP_PORT, DASH_PORT):
        s = socket.socket(); r = s.connect_ex(('127.0.0.1', port)); s.close()
        results.append((f'ST-01-{port}', 'WARN' if r == 0 else 'PASS',
                        f'Порт {port} {"занят" if r == 0 else "свободен"}'))
    try:
        from neva_mcp_events import push_event
        from neva_mcp_patch  import apply_patch
        results.append(('ST-02', 'PASS', 'modules OK'))
    except Exception as e: results.append(('ST-02', 'FAIL', str(e)))
    try:
        st = _get_neva_status()
        assert st['status'] == 'ok'
        results.append(('ST-03', 'PASS', 'neva_status OK'))
    except Exception as e: results.append(('ST-03', 'FAIL', str(e)))
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write('v=1.0\n'); tmp = f.name
    r = _execute_action('file_patch', {'path': tmp, 'diff': '@@ -1,1 +1,1 @@\n-v=1.0\n+v=2.0\n'})
    ok = r.get('status') == 'ok' and 'v=2.0' in Path(tmp).read_text()
    _os.unlink(tmp)
    results.append(('ST-04', 'PASS' if ok else 'FAIL', 'file_patch action'))
    try:
        init_req  = {'jsonrpc':'2.0','id':1,'method':'initialize',
                     'params':{'protocolVersion':'2024-11-05','capabilities':{}}}
        init_resp = _handle_jsonrpc(init_req)
        assert init_resp['result']['protocolVersion'] == '2024-11-05'
        list_req  = {'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}}
        list_resp = _handle_jsonrpc(list_req)
        assert list_resp['result']['tools'][0]['name'] == 'neva_execute'
        results.append(('ST-05', 'PASS', 'JSON-RPC initialize + tools/list OK'))
    except Exception as e: results.append(('ST-05', 'FAIL', str(e)))
    tok = _load_token()
    results.append(('ST-06', 'PASS' if tok else 'WARN',
                    f'token {"ok" if tok else "not set"} ({len(tok)} chars)'))
    try:
        html = _build_dashboard_html()
        assert 'NEVA Live Dashboard v2.0' in html
        results.append(('ST-07', 'PASS', f'Dashboard HTML {len(html)}b'))
    except Exception as e: results.append(('ST-07', 'FAIL', str(e)))
    return results


# ─── MAIN ───────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if '--self-test' in sys.argv:
        print('=== NEVA MCP Server v2.0 (Streamable HTTP) self-test ===')
        res = self_test()
        passed = sum(1 for _, s, _ in res if s == 'PASS')
        warns  = sum(1 for _, s, _ in res if s == 'WARN')
        for n, s, m in res:
            print(f'  {"✅" if s == "PASS" else "⚠️" if s == "WARN" else "❌"} {n}: {m}')
        print(f'\nРезультат: {passed}/{len(res)} PASS ({warns} предупреждений)')
        sys.exit(0 if passed + warns == len(res) else 1)

    for port in (MCP_PORT, DASH_PORT):
        s = socket.socket()
        if s.connect_ex(('127.0.0.1', port)) == 0:
            s.close()
            log.error(f'Порт {port} занят! Остановите старый экземпляр.')
            sys.exit(1)
        s.close()

    log.info('NEVA MCP Server v2.0 (Streamable HTTP) starting...')
    dash = HTTPServer(('127.0.0.1', DASH_PORT), DashboardHandler)
    threading.Thread(target=dash.serve_forever, daemon=True).start()
    log.info(f'Дашборд запущен: http://127.0.0.1:{DASH_PORT}')
    print(f'🔷 NEVA MCP Server v2.0 (Streamable HTTP)')
    print(f'   MCP endpoint: http://127.0.0.1:{MCP_PORT}/mcp')
    print(f'   Dashboard:    http://127.0.0.1:{DASH_PORT}')
    HTTPServer(('127.0.0.1', MCP_PORT), MCPHandler).serve_forever()
