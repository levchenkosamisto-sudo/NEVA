"""
NEVA ПАМЯТЬ v3 — Rate Limiter с ротацией провайдеров
src/memory/rate_limiter.py

Лимиты (бесплатные планы):
  Церебрас gpt-oss-120b:  1  RPM
  Грок llama-3.3-70b:    30  RPM
  DeepSeek:              60  RPM
"""
import time, logging, os, re
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("neva.rate_limiter")


@dataclass
class Provider:
    name: str
    rpm: int
    priority: int
    requests_this_min: int = 0
    window_start: float = field(default_factory=time.time)
    locked_until: float = 0.0

    @property
    def min_interval(self) -> float:
        return 60.0 / self.rpm

    def is_available(self) -> bool:
        now = time.time()
        if now < self.locked_until:
            return False
        if now - self.window_start >= 60.0:
            self.requests_this_min = 0
            self.window_start = now
        return self.requests_this_min < self.rpm

    def record(self):
        now = time.time()
        if now - self.window_start >= 60.0:
            self.requests_this_min = 0
            self.window_start = now
        self.requests_this_min += 1
        log.debug("[%s] %d/%d RPM", self.name, self.requests_this_min, self.rpm)

    def lock(self, secs: float = 60.0):
        self.locked_until = time.time() + secs
        log.warning("[%s] locked %.0fс", self.name, secs)

    def wait_secs(self) -> float:
        now = time.time()
        if now < self.locked_until:
            return self.locked_until - now
        if now - self.window_start >= 60.0:
            return 0.0
        if self.requests_this_min >= self.rpm:
            return 60.0 - (now - self.window_start)
        return 0.0


PROVIDERS = [
    Provider(name="cerebras", rpm=1,  priority=1),
    Provider(name="groq",     rpm=30, priority=2),
    Provider(name="deepseek", rpm=60, priority=3),
]

_last_req: dict[str, float] = {}


def call_with_rate_limit(prompt: str, max_tokens: int = 1000) -> Optional[str]:
    """Вызов ИИ с rate limiting и авторотацией провайдеров."""
    for attempt in range(len(PROVIDERS) * 3):
        # Ищем доступного
        provider = None
        for p in sorted(PROVIDERS, key=lambda x: x.priority):
            if p.is_available():
                provider = p
                break

        if provider is None:
            # Все заняты — ждём ближайшего
            waits = [p.wait_secs() for p in PROVIDERS]
            w = max(1.0, min(waits))
            log.info("[RATE] все заняты, ждём %.0fс", w)
            time.sleep(min(w, 10.0))
            continue

        # Выдерживаем интервал
        last = _last_req.get(provider.name, 0)
        need = provider.min_interval - (time.time() - last)
        if need > 0:
            log.debug("[%s] пауза %.1fс", provider.name, need)
            time.sleep(need)

        try:
            result = _call(provider.name, prompt, max_tokens)
            _last_req[provider.name] = time.time()
            provider.record()
            return result
        except Exception as e:
            err = str(e).lower()
            is_rl = any(x in err for x in ['429','rate limit','too many','quota'])
            retry = _parse_retry(str(e))
            provider.lock(retry if is_rl else 15.0)
            log.warning("[%s] %s → locked %.0fс", provider.name,
                        "429" if is_rl else "error", retry if is_rl else 15.0)

    log.error("[RATE] все попытки исчерпаны")
    return None


def _call(name: str, prompt: str, max_tokens: int) -> str:
    if name == "cerebras":
        from cerebras.cloud.sdk import Cerebras
        r = Cerebras(api_key=os.environ.get("CEREBRAS_API_KEY","")).chat.completions.create(
            model="gpt-oss-120b",
            messages=[{"role":"user","content":prompt}],
            max_tokens=max_tokens)
        return r.choices[0].message.content

    if name == "groq":
        from groq import Groq
        r = Groq(api_key=os.environ.get("GROQ_API_KEY","")).chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            max_tokens=max_tokens)
        return r.choices[0].message.content

    if name == "deepseek":
        import urllib.request, json as _j
        payload = _j.dumps({"model":"deepseek-chat",
            "messages":[{"role":"user","content":prompt}],
            "max_tokens":max_tokens}).encode()
        req = urllib.request.Request(
            "https://api.deepseek.com/chat/completions", data=payload,
            headers={"Content-Type":"application/json",
                     "Authorization":f"Bearer {os.environ.get('DEEPSEEK_API_KEY','')}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return _j.loads(resp.read())["choices"][0]["message"]["content"]

    raise ValueError(f"Неизвестный провайдер: {name}")


def _parse_retry(err: str) -> float:
    for pat in [r'retry.{0,10}after[:\s]+(\d+)', r'wait[:\s]+(\d+)', r'(\d+)\s*second']:
        m = re.search(pat, err.lower())
        if m:
            return float(m.group(1))
    return 60.0


def status() -> dict:
    now = time.time()
    return {p.name: f"LOCKED {p.locked_until-now:.0f}с" if now < p.locked_until
            else f"OK {p.requests_this_min}/{p.rpm} RPM"
            for p in PROVIDERS}
