# AUDIT-001 Round 2 — CEREBRAS
Дата: 2026-06-22 06:46:20

## NEVA — Independent Technical Audit (Circle 2)

Below you will find a **point‑by‑point assessment** that directly follows the questions that were raised in **Circle 1** (the “questions‑list” that the audit team submitted).  
For each item I give:

| # | Item / Question (as asked in Circle 1) | Verdict | Criticality | If **Insufficient / Risk** → What‑to‑do (best‑practice solution) |
|---|----------------------------------------|---------|------------|--------------------------------------------------------------|

> **Legend**  
> *Verdict* – **DOSTATOCHNO** (sufficient), **NEDOSTATOCHNO** (insufficient), **RISK** (acceptable now but with a clear danger).  
> *Criticality* – **LOW**, **MEDIUM**, **HIGH**, **BLOCKER** (must be fixed before production).  

---

### 1. Architecture – FlagmanRouter (Cerebras → Groq → GitHub Models → OpenRouter×2 → qwen2.5:7b → llama3.2:3b)

| # | Question (Circle 1) | Verdict | Criticality | Recommended action |
|---|----------------------|---------|------------|--------------------|
| 1.1 | **Is the routing logic deterministic and auditable?** | **NEDOSTATOCHNO** | **HIGH** | • Introduce a **routing manifest** (YAML/JSON) that lists every possible path, weight, fallback rule and version hash of each model. <br>• Log every request/response pair with a **correlation ID** that is stored in a tamper‑evident audit log (e.g., append‑only file + digital signature). |
| 1.2 | **Are version mismatches between providers handled?** | **RISK** | **MEDIUM** | • Add a **compatibility matrix** that maps provider API versions → supported model features. <br>• Fail‑fast on mismatch and trigger Medic L2 with a detailed error. |
| 1.3 | **Is there protection against request amplification (e.g., loops between OpenRouter instances)?** | **RISK** | **HIGH** | • Add a **hop‑counter** (max = 5) to the request metadata; reject any request that exceeds the limit. <br>• Instrument a “loop‑detector” that watches for repeated source‑destination pairs. |
| 1.4 | **Are fallback mechanisms (e.g., when qwen2.5 runs out of RAM) safe?** | **NEDOSTATOCHNO** | **HIGH** | • Implement **state‑machine‑driven fallback** (e.g., “PRIMARY → SECONDARY → TERTIARY”) that is part of the ThermalGuard FSM. <br>• Persist fallback decisions to the audit DB so they can be replayed in case of a crash. |

---

### 2. ThermalGuard v9.4 – FSM (9 states, 32/34 PASS, 2 FAIL)

| # | Question (Circle 1) | Verdict | Criticality | Recommended action |
|---|----------------------|---------|------------|--------------------|
| 2.1 | **What caused the two failures (race‑condition EMERGENCY → RECOVERY)?** | **RISK** | **BLOCKER** | • Add **atomic state transitions** using `asyncio.Lock` (or `asyncio.Condition`) around every FSM edge. <br>• Create a **unit‑test harness** that spawns 100 concurrent “temperature spikes” and verifies that only one thread can drive the EMERGENCY→RECOVERY transition. |
| 2.2 | **Is the FSM observable (metrics/alerts)?** | **NEDOSTATOCHNO** | **MEDIUM** | • Expose a **Prometheus exporter** for each state (counter of entries/exits). <br>• Hook the exporter into the Dashboard (port 9001) and set alerts for rapid state churn (> 3 state changes / sec). |
| 2.3 | **Does the FSM survive a hard‑reset (e.g., power loss)?** | **RISK** | **HIGH** | • Persist the **last known safe state** to a small, write‑protected file (`/var/lib/neva/thermal_state.json`) on every transition. <br>• On boot, read the file and resume from that state, falling back to **RECOVERY** if the file is corrupted. |
| 2.4 | **Are state‑timeouts correctly tuned for an M1‑Mac (thermal envelope)?** | **NEDOSTATOCHNO** | **LOW** | • Run a **thermal profiling suite** (Apple’s Instruments → Energy) for each workload, then adjust the timeout values in the FSM configuration accordingly. |

---

### 3. Medic L1/L2/L3 (Self‑Healing)

| # | Question (Circle 1) | Verdict | Criticality | Recommended action |
|---|----------------------|---------|------------|--------------------|
| 3.1 | **Are the escalation policies clearly defined?** | **NEDOSTATOCHNO** | **MEDIUM** | • Document a **run‑book** that maps each failure type → L1/L2/L3 actions, time‑outs and responsible owner. <br>• Store the run‑book in the same repo as the code (version‑controlled). |
| 3.2 | **Is L3 = Claude safe for “CHRONIC” failures (potentially sensitive data)?** | **RISK** | **HIGH** | • Enable **data redaction** before forwarding any request to Claude (remove PII/PHI). <br>• Log any redacted fields and verify with a compliance reviewer. |
| 3.3 | **Does L2 repair attempt to mutate external services (Cerebras/Groq) without idempotency?** | **RISK** | **HIGH** | • Wrap every external call in a **transactional wrapper** that records “attempted repair” and can be **re‑tried** safely. <br>• If the provider does not support idempotent repair, implement a **no‑op shim** that only simulates a repair. |

---

### 4. MCP Server v2.4 (Ports 9000 JSON‑RPC, 9001 Dashboard)

| # | Question (Circle 1) | Verdict | Criticality | Recommended action |
|---|----------------------|---------|------------|--------------------|
| 4.1 | **Is authentication/authorization enforced on both ports?** | **NEDOSTATOCHNO** | **BLOCKER** | • Add **mutual‑TLS** (mTLS) for the JSON‑RPC endpoint. <br>• Require **JWT‑based RBAC** for Dashboard users; reject anonymous requests. |
| 4.2 | **Are rate‑limits applied to prevent DoS?** | **RISK** | **HIGH** | • Implement a **token bucket** per client IP (default 10 req/s). <br>• Expose the current bucket status via the Dashboard. |
| 4.3 | **Does the server validate JSON‑RPC payload schema?** | **NEDOSTATOCHNO** | **MEDIUM** | • Use **pydantic/fastjsonschema** to enforce strict request/response schemas. |
| 4.4 | **Is the server resilient to malformed packets (e.g., oversized frames)?** | **RISK** | **HIGH** | • Set a **maximum payload size** (e.g., 256 KB). <br>• Gracefully close the socket on violation and log the incident. |

---

### 5. Kuzu Graph DB – “atoms” P16 (8 fields) + Write‑Queue `asyncio.Lock`

| # | Question (Circle 1) | Verdict | Criticality | Recommended action |
|---|----------------------|---------|------------|--------------------|
| 5.1 | **Is the `asyncio.Lock` sufficient for high‑concurrency writes?** | **RISK** | **HIGH** | • Replace the single lock with a **sharded lock pool** (e.g., one lock per atom‑type). <br>• If write‑throughput > 500 ops/s, consider **optimistic concurrency control** (version stamps) with retry logic. |
| 5.2 | **Are schema migrations audited?** | **NEDOSTATOCHNO** | **MEDIUM** | • Introduce a **migration tool** (Alembic‑style) that stores each migration script’s hash in a separate audit table. |
| 5.3 | **Is backup / restore tested?** | **RISK** | **HIGH** | • Create a **daily snapshot** of the graph DB (Kuzu supports `dump`) and push it to an encrypted S3‑compatible bucket. <br>• Validate restore on a staging node weekly. |
| 5.4 | **Are query time‑outs enforced?** | **NEDOSTATOCHNO** | **LOW** | • Configure a **max‑execution‑time** (e.g., 2 s) on the DB driver; abort long‑running queries and surface a clear error to the caller. |

---

### 6. DUMA – GitHub input/output polling audit

| # | Question (Circle 1) | Verdict | Criticality | Recommended action |
|---|----------------------|---------|------------|--------------------|
| 6.1 | **Is the polling interval configurable?** | **NEDOSTATOCHNO** | **LOW** | • Expose a **`DUMA_POLL_INTERVAL`** env‑var (default 30 s) and enforce a minimum (5 s) to avoid API‑rate limits. |
| 6.2 | **Are GitHub‑webhook signatures verified?** | **RISK** | **HIGH** | • Switch from polling to **webhook delivery** (GitHub supports signed payloads). <br>• If polling must stay, always verify the **`X-Hub-Signature-256`** header. |
| 6.3 | **Does DUMA handle merge‑conflict scenarios?** | **RISK** | **MEDIUM** | • Add a **conflict‑resolution hook** that automatically creates a “manual‑review” ticket in the system when a conflict is detected. |
| 6.4 | **Is audit data stored tamper‑evidently?** | **NEDOSTATOCHNO** | **MEDIUM** | • Append each audit entry to an **append‑only log** and sign the log periodically (e.g., every 10 k entries) with a server‑side private key. |

---

### 7. Approval Gate :8766 – blocks sudo/delete/deploy/paid‑API

| # | Question (Circle 1) | Verdict | Criticality | Recommended action |
|---|----------------------|---------|------------|--------------------|
| 7.1 | **Are the blocked commands enforced at OS level or just in‑process?** | **RISK** | **BLOCKER** | • Enforce the gate via **Linux Capabilities** (or macOS equivalent **Seatbelt sandbox**) rather than a pure‑Python check. <br>• Run the NEVA process as a **non‑root** user; `sudo` should never be reachable. |
| 7.2 | **Is the list of “paid API” endpoints up‑to‑date?** | **NEDOSTATOCHNO** | **MEDIUM** | • Maintain a **central manifest** (JSON) that lists every paid‑endpoint (including version). <br>• CI‑pipeline should validate that no new endpoint is added without a gate‑rule entry. |
| 7.3 | **Is there an audit trail for every gate‑rejection?** | **NEDOSTATOCHNO** | **HIGH** | • Log every rejected request with **user, timestamp, operation, and reason** to an immutable store (e.g., write‑once journal). |
| 7.4 | **Does the gate support temporary overrides (e.g., for emergency patches)?** | **NEDOSTATOCHNO** | **LOW** | • Add a **“break‑glass”** procedure that requires multi‑person approval (e.g., two signed JWTs) and logs the override for 30 days. |

---

### 8. Exponential Backoff (60 s → 5 m → 15 m → 30 m → 1 h + CHRONIC detection)

| # | Question (Circle 1) | Verdict | Criticality | Recommended action |
|---|----------------------|---------|------------|--------------------|
| 8.1 | **Is the back‑off reset after a successful call?** | **NEDOSTATOCHNO** | **MEDIUM** | • Implement a **state reset** that clears the back‑off series on any successful request (or after a configurable “cool‑down” period). |
| 8.2 | **Are “CHRONIC” detections (persistent failures) escalated to Medic L3?** | **RISK** | **HIGH** | • Add a **failure‑counter** that, after *N* consecutive back‑off cycles (default 5), triggers the L3 pathway automatically. |
| 8.3 | **Does the back‑off respect per‑endpoint rate limits?** | **NEDOSTATOCHNO** | **LOW** | • Store each endpoint’s **max‑rate** in a config file; back‑off algorithm should consider the most restrictive limit. |
| 8.4 | **Is there a risk of “thundering herd” when multiple components retry simultaneously?** | **RISK** | **MEDIUM** | • Add a **jitter** (± 10 % random) to each back‑off interval. |

---

### 9. RAM Allocation – qwen2.5:7b (8 GB) **OR** e5‑small RAG (2 GB) – mutually exclusive

| # | Question (Circle 1) | Verdict | Criticality | Recommended action |
|---|----------------------|---------|------------|--------------------|
| 9.1 | **Is the mutual‑exclusion enforced at runtime?** | **RISK** | **BLOCKER** | • Implement a **singleton resource manager** that acquires a lock on startup; if the wrong model is already loaded, abort with a clear error. |
| 9.2 | **Are memory‑pressure events (e.g., macOS low‑memory warnings) handled?** | **NEDOSTATOCHNO** | **HIGH** | • Subscribe to macOS **`NSProcessInfo.powerStateDidChangeNotification`** (or use `psutil` to watch `available_memory`). <br>• When free RAM < 1 GB, trigger a graceful unload of the heavy model and fall back to e5‑small automatically. |
| 9.3 | **Is the model‑swap latency measured and logged?** | **NEDOSTATOCHNO** | **MEDIUM** | • Add a **timer** around the model load/unload sequence; store the latency in the telemetry DB for capacity planning. |
| 9.4 | **Does the system protect against OOM crashes (e.g., by using `resource.setrlimit`)?** | **RISK** | **BLOCKER** | • Set a **process‑wide memory limit** (`RLIMIT_AS`) slightly below the physical RAM (e.g., 7 GB) to guarantee the OS will kill the process cleanly before the entire machine freezes. |

---

### 10. Unfinished / TODO Items  

| # | Item | Verdict | Criticality | Recommended action |
|---|------|---------|------------|--------------------|
| 10.1 | **Graphiti (MockGraph)** – placeholder for future graph engine | **NEDOSTATOCHNO** | **MEDIUM** | • Document a **feature flag** that disables any code paths that still reference Graphiti. <br>• Write unit tests that verify the flag prevents accidental execution. |
| 10.2 | **e5‑small (RAG) – not yet integrated** | **RISK** | **HIGH** | • Create a **staging branch** where the e5‑small model is loaded and its inference latency/accuracy profiled. <br>• Only merge to `main` after meeting SLA (≤ 150 ms inference). |
| 10.3 | **TTL (time‑to‑live) cache for query results** | **NEDOSTATOCHNO** | **LOW** | • Add a simple **LRU‑TTL cache** (e.g., `