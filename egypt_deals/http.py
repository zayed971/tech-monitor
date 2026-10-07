"""Rate limiting, disk cache, redirect checks and robots with wildcard rules."""
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx

USER_AGENT = "EgyptDealTracker/0.1 (personal price monitoring; no purchases)"

class FetchError(Exception):
    pass

class Robots:
    def __init__(self, text):
        groups, agents, rules, delay = [], [], [], 0
        seen_directive = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line: continue
            key, value = (x.strip() for x in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if seen_directive:
                    groups.append((agents, rules, delay))
                    agents, rules, delay, seen_directive = [], [], 0, False
                agents.append(value.lower())
            elif agents and key in {"allow", "disallow", "crawl-delay"}:
                seen_directive = True
                if key == "crawl-delay":
                    try: delay = max(delay, float(value))
                    except ValueError: pass
                elif value: rules.append((key == "allow", value))
        groups.append((agents, rules, delay))
        specific = [g for g in groups if any(a != "*" and a in USER_AGENT.lower() for a in g[0])]
        selected = specific or [g for g in groups if "*" in g[0]]
        self.rules = [r for g in selected for r in g[1]]
        self.delay = max([g[2] for g in selected] or [0])

    def allows(self, url):
        p = urlsplit(url)
        path = p.path + ("?" + p.query if p.query else "")
        matches = []
        for allowed, pattern in self.rules:
            anchored = pattern.endswith("$")
            pattern_body = pattern[:-1] if anchored else pattern
            regex = re.escape(pattern_body).replace(r"\*", ".*")
            if any(re.match(regex + ("$" if anchored else ""), candidate) for candidate in [path, unquote(path)]):
                matches.append((len(pattern_body.replace("*", "")), allowed))
        return max(matches)[1] if matches else True

class Client:
    def __init__(self, cache_dir, delay=4, ttl=1800):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay, self.ttl = delay, ttl
        self.http = httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}, follow_redirects=False)
        self.robots, self.last, self.blocked = {}, {}, set()
        self.requests = 0

    def close(self):
        self.http.close()

    def _request(self, url):
        origin = "{0.scheme}://{0.netloc}".format(urlsplit(url))
        host = urlsplit(url).hostname.removeprefix("www.")
        if host in self.blocked: raise FetchError("host paused after access/rate-limit failure")
        extra = getattr(self, "slow", {})
        for attempt in range(3):
            delay = max(self.delay, self.robots.get(origin, Robots("")).delay) * extra.get(host, 1)
            time.sleep(max(0, delay - (time.monotonic() - self.last.get(host, 0))))
            try:
                response = self.http.get(url)
            except httpx.HTTPError:
                raise FetchError("network or TLS error") from None
            finally:
                self.last[host] = time.monotonic()
            self.requests += 1
            if response.status_code != 429 or attempt == 2: break
            # Rate limited: slow down for this host (doubling, up to 8x) and wait out Retry-After (at most 90 s) before one retry.
            self.slow = extra = {**extra, host: min(8, extra.get(host, 1) * 2)}
            wait = response.headers.get("retry-after", "")
            time.sleep(min(90, int(wait)) if wait.isdigit() else 30)
        if response.status_code in {401, 403, 429}:
            self.blocked.add(host)
        return response

    def _robots(self, origin):
        if origin in self.robots: return self.robots[origin]
        url = origin + "/robots.txt"
        for _ in range(4):
            r = self._request(url)
            if r.is_redirect:
                url = urljoin(url, r.headers["location"])
                if urlsplit(url).path != "/robots.txt": raise FetchError("robots redirected away from robots.txt")
                continue
            if r.status_code in {404, 410}:
                policy = Robots("")
            elif r.status_code == 200 and not r.text.lstrip().startswith("<"):
                policy = Robots(r.text)
            else:
                raise FetchError(f"robots unavailable: HTTP {r.status_code}")
            self.robots[origin] = policy
            return policy
        raise FetchError("robots redirect limit")

    def get(self, url, *, private=False):
        if urlsplit(url).scheme not in {"http", "https"}: raise FetchError("unsupported URL")
        key = hashlib.sha256(url.encode()).hexdigest()
        cache = self.cache_dir / (key + ".json")
        for _ in range(5):
            origin = "{0.scheme}://{0.netloc}".format(urlsplit(url))
            if not self._robots(origin).allows(url): raise FetchError("robots.txt disallows requested URL")
            if not private and cache.exists():
                saved = json.loads(cache.read_text())
                if time.time() - saved["time"] < self.ttl:
                    return saved["body"], saved["url"], saved["observed_at"]
            r = self._request(url)
            if r.is_redirect:
                url = urljoin(url, r.headers["location"])
                continue
            if r.status_code != 200: raise FetchError(f"HTTP {r.status_code}")
            if any(t in r.text[:5000].lower() for t in ["just a moment...", "cf-chl-", "verify you are human"]):
                raise FetchError("access challenge")
            from .model import now
            observed = now()
            if not private:
                cache.write_text(json.dumps({"time":time.time(), "url":str(r.url), "observed_at":observed,"body":r.text}))
            return r.text, str(r.url), observed
        raise FetchError("redirect limit")
