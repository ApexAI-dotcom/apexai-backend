"""
Récupération polie des pages publiques.

- robots.txt lu et respecté avant toute page d'un domaine (absent = autorisé,
  illisible = on s'abstient) ;
- identification honnête : ApexAIBot, avec une page qui explique le robot ;
- une requête au plus toutes les DELAY_S secondes par domaine ;
- cache disque : une page déjà lue depuis moins de `max_age_h` n'est pas
  redemandée ;
- jamais de contournement : pas de navigateur furtif, pas d'usurpation
  d'empreinte TLS, pas de résolution de captcha. Un refus (401, 403, 429,
  captcha) arrête la collecte de ce domaine et se note dans le journal.
- domaines interdits par principe : LinkedIn, Instagram, Facebook, TikTok.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional
from urllib.parse import urlparse

USER_AGENT = "ApexAIBot/1.0 (+https://www.apexai.racing; contact@apexai.racing)"
DELAY_S = 4.0
FORBIDDEN_DOMAINS = ("linkedin.com", "instagram.com", "facebook.com", "tiktok.com", "x.com", "twitter.com")


class Refused(Exception):
    """La source refuse (robots.txt, 401/403/429, captcha) : on s'arrête là."""


@dataclass
class PoliteFetcher:
    cache_dir: Path
    http_get: Optional[Callable[[str, Dict[str, str]], "tuple[int, str]"]] = None
    delay_s: float = DELAY_S
    log: list = field(default_factory=list)
    _last: Dict[str, float] = field(default_factory=dict)
    _robots: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = field(default_factory=dict)
    _blocked: set = field(default_factory=set)

    def __post_init__(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.http_get is None:
            self.http_get = _httpx_get

    # ── garde-fous ──────────────────────────────────────────────────────
    def _domain(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    def _check_domain(self, url: str) -> str:
        d = self._domain(url)
        if any(d == f or d.endswith("." + f) for f in FORBIDDEN_DOMAINS):
            raise Refused(f"{d} : domaine exclu par principe (conditions d'utilisation)")
        if d in self._blocked:
            raise Refused(f"{d} : collecte arrêtée après un refus")
        return d

    def _allowed_by_robots(self, url: str) -> bool:
        d = self._domain(url)
        if d not in self._robots:
            robots_url = f"{urlparse(url).scheme}://{d}/robots.txt"
            status, body = self._throttled_get(robots_url)
            if status == 404 or status == 410:
                self._robots[d] = None  # pas de robots.txt : rien d'interdit
            elif status == 200:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(body.splitlines())
                self._robots[d] = rp
            else:
                self._blocked.add(d)  # robots.txt illisible : prudence
                self._note("robots_illisible", robots_url, status)
                return False
        rp = self._robots[d]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    # ── requêtes ────────────────────────────────────────────────────────
    def _throttled_get(self, url: str) -> "tuple[int, str]":
        d = self._domain(url)
        wait = self._last.get(d, 0) + self.delay_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last[d] = time.monotonic()
        return self.http_get(url, {"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"})

    def get(self, url: str, max_age_h: float = 24.0) -> str:
        self._check_domain(url)
        key = hashlib.sha256(url.encode()).hexdigest()[:24]
        cached = self.cache_dir / f"{key}.json"
        if cached.exists():
            data = json.loads(cached.read_text())
            if time.time() - data["at"] < max_age_h * 3600:
                self._note("cache", url, 200)
                return data["body"]
        if not self._allowed_by_robots(url):
            self._note("interdit_robots", url, None)
            raise Refused(f"{url} : interdit par robots.txt")
        status, body = self._throttled_get(url)
        if status in (401, 403, 429) or _looks_like_captcha(body):
            self._blocked.add(self._domain(url))
            self._note("refus", url, status)
            raise Refused(f"{url} : la source refuse ({status})")
        if status != 200:
            self._note("erreur", url, status)
            raise RuntimeError(f"{url} : statut {status}")
        cached.write_text(json.dumps({"at": time.time(), "url": url, "body": body}))
        self._note("lu", url, status)
        return body

    def _note(self, event: str, url: str, status):
        self.log.append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, "url": url, "status": status})


def _looks_like_captcha(body: str) -> bool:
    b = (body or "")[:20000].lower()
    return any(m in b for m in ("g-recaptcha\" data-sitekey", "cf-challenge", "hcaptcha.com/captcha", "verify you are human"))


def _httpx_get(url: str, headers: Dict[str, str]) -> "tuple[int, str]":
    import httpx
    r = httpx.get(url, headers=headers, timeout=20.0, follow_redirects=True)
    return r.status_code, r.text
