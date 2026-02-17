# blocks.py
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re

_LINK_LAST_RE = re.compile(r'rel="last"', re.IGNORECASE)
_LINK_PAGE_RE = re.compile(r"[?&]page=(\d+)")


def _parse_link_last_page(link_header: str) -> Optional[int]:
    """
    GitHub uses RFC5988 Link header for pagination.
    If we request per_page=1, the 'last' page number == total commits.
    """
    if not link_header:
        return None
    parts = [p.strip() for p in link_header.split(",") if p.strip()]
    for p in parts:
        if _LINK_LAST_RE.search(p):
            m = _LINK_PAGE_RE.search(p)
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    return None
    return None

# ----------------- small utils -----------------

def now_ts() -> float:
    return time.time()

def _safe_str(v: Any, n: int = 256) -> str:
    s = "" if v is None else str(v)
    s = s.replace("\r", " ").replace("\n", " ")
    return s if len(s) <= n else s[:n]

def _clamp_int(v: Any, lo: int, hi: int, default: int = 0) -> int:
    try:
        x = int(v)
    except Exception:
        return default
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x

def app_dir() -> Path:
    # local per-user config folder
    p = Path.home() / ".githubanalyticsProject"
    p.mkdir(parents=True, exist_ok=True)
    return p

def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")

def _traffic_total_from_series(resp: Any, series_key: str) -> int:
    """
    GitHub traffic endpoints return:
      { "count": N, "uniques": U, "<series_key>": [ {timestamp,count,uniques}, ... ] }

    Sometimes you’ll see count=0 if permissions fail or data is partial; we fallback
    to summing the series counts when available.
    """
    if not isinstance(resp, dict):
        return 0
    base = _clamp_int(resp.get("count"), 0, 2_000_000_000, 0)
    series = resp.get(series_key)
    if isinstance(series, list) and series:
        s = 0
        for it in series:
            if isinstance(it, dict):
                s += _clamp_int(it.get("count"), 0, 2_000_000_000, 0)
        # prefer the larger number if GitHub returns a weird 0
        return max(base, s)
    return base

# ----------------- block registry -----------------

class Registry:
    def __init__(self) -> None:
        self._blocks: Dict[str, Any] = {}

    def register(self, name: str, cls: Any) -> None:
        self._blocks[name] = cls

    def get(self, name: str) -> Any:
        return self._blocks[name]

    def has(self, name: str) -> bool:
        return name in self._blocks

BLOCKS = Registry()

def block(name: str):
    def deco(cls):
        BLOCKS.register(name, cls)
        return cls
    return deco


@dataclass
class BaseBlock:
    def execute(self, payload: Any, *, params: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        raise NotImplementedError


# ----------------- GitHub API client -----------------

class GitHubClient:
    """
    Minimal GitHub REST client using urllib (no extra deps).
    Handles:
      - public endpoints without token
      - private/traffic endpoints with token
    """
    def __init__(self, token: str = "", user_agent: str = "githubanalyticsProject") -> None:
        self.token = token.strip()
        self.user_agent = user_agent

    def _make_req(self, url: str, accept: str) -> urllib.request.Request:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", self.user_agent)
        req.add_header("Accept", accept)
        # recommended by GitHub docs for REST versioning
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        return req

    def get_json(self, url: str, *, accept: str = "application/vnd.github+json") -> Any:
        data, _headers = self.get_json_with_headers(url, accept=accept)
        return data

    def get_json_with_headers(self, url: str, *, accept: str = "application/vnd.github+json") -> Tuple[Any, Dict[str, str]]:
        req = self._make_req(url, accept)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                headers = {k: v for (k, v) in resp.headers.items()}
            return json.loads(raw.decode("utf-8", "replace")), headers
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", "replace")
            except Exception:
                body = ""
            raise RuntimeError(f"GitHub API HTTP {e.code}: {url}\n{body[:4000]}")
        except Exception as e:
            raise RuntimeError(f"GitHub API error: {url}\n{e}")



def parse_repo_slug(s: str) -> Optional[Tuple[str, str]]:
    s = (s or "").strip()
    if not s:
        return None
    s = s.replace("https://github.com/", "").strip("/")
    if "/" not in s:
        return None
    owner, name = s.split("/", 1)
    owner = owner.strip()
    name = name.strip()
    if not owner or not name:
        return None
    return owner, name


# ----------------- blocks -----------------

@block("config_load")
@dataclass
class ConfigLoadBlock(BaseBlock):
    """
    Loads config from ~/.githubanalyticsProject/config.json
    """
    def execute(self, payload: Any, *, params: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        cfg_path = Path(params.get("path") or (app_dir() / "config.json"))
        cfg = load_json(cfg_path, default={})
        return cfg, {"config_path": str(cfg_path)}


@block("config_save")
@dataclass
class ConfigSaveBlock(BaseBlock):
    """
    Saves config to ~/.githubanalyticsProject/config.json
    """
    def execute(self, payload: Any, *, params: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        cfg_path = Path(params.get("path") or (app_dir() / "config.json"))
        save_json(cfg_path, payload if isinstance(payload, dict) else {})
        return payload, {"saved_to": str(cfg_path)}


@block("github_fetch")
@dataclass
class GitHubFetchBlock(BaseBlock):
    """
    Fetch analytics for repos.

    Input payload:
      {
        "repos": ["owner/name", "https://github.com/owner/name", ...],
        "token": "..." (optional),
      }

    Output:
      {
        "generated_at": ts,
        "repos": [ {repo_analytics...}, ... ],
        "errors": [ {repo, error}, ... ],
      }
    """
    def execute(self, payload: Any, *, params: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        payload = payload if isinstance(payload, dict) else {}
        repos_in = payload.get("repos") or []
        token = (payload.get("token") or "").strip() or (os.environ.get("GITHUB_TOKEN") or "").strip()

        # allow params override
        if params.get("token") is not None:
            token = str(params.get("token") or "").strip()

        client = GitHubClient(token=token)

        out: Dict[str, Any] = {"generated_at": now_ts(), "repos": [], "errors": []}
        meta: Dict[str, Any] = {"token_provided": bool(token), "count": 0}

        for r in repos_in:
            slug = parse_repo_slug(str(r))
            if not slug:
                out["errors"].append({"repo": str(r), "error": "invalid_repo_slug"})
                continue
            owner, name = slug
            full = f"{owner}/{name}"

            try:
                repo_url = f"https://api.github.com/repos/{owner}/{name}"
                repo = client.get_json(repo_url)
                # commits total (public): use per_page=1 and parse Link: rel="last"
                # commits total (public): request per_page=1 and parse Link: rel="last"
                commits_total = 0
                commits_err = ""
                try:
                    q = f"{repo_url}/commits?per_page=1"
                    commits_json, headers = client.get_json_with_headers(q)
                    if isinstance(commits_json, list):
                        link = headers.get("Link") or headers.get("link") or ""
                        last_page = _parse_link_last_page(link)
                        if last_page is not None:
                            commits_total = int(last_page)
                        else:
                            commits_total = len(commits_json)
                except Exception as e:
                    commits_total = 0
                    commits_err = _safe_str(str(e), 1200)
                # languages (public)
                langs = {}
                try:
                    langs = client.get_json(f"{repo_url}/languages")
                except Exception:
                    langs = {}

                # releases + download totals (public)
                releases: List[Dict[str, Any]] = []
                page = 1
                while True:
                    rel_url = f"{repo_url}/releases?per_page=100&page={page}"
                    chunk = client.get_json(rel_url)
                    if not isinstance(chunk, list) or not chunk:
                        break
                    releases.extend([x for x in chunk if isinstance(x, dict)])
                    if len(chunk) < 100:
                        break
                    page += 1
                    if page > 20:  # safety
                        break

                total_asset_downloads = 0
                per_release = []
                for rel in releases:
                    assets = rel.get("assets") or []
                    rel_sum = 0
                    for a in assets:
                        if isinstance(a, dict):
                            rel_sum += _clamp_int(a.get("download_count"), 0, 2_000_000_000, 0)
                    total_asset_downloads += rel_sum
                    per_release.append({
                        "tag": _safe_str(rel.get("tag_name") or "", 128),
                        "name": _safe_str(rel.get("name") or "", 256),
                        "published_at": _safe_str(rel.get("published_at") or "", 64),
                        "assets_count": len(assets) if isinstance(assets, list) else 0,
                        "assets_downloads": rel_sum,
                    })

                # traffic endpoints (require token + write/admin on repo)
                traffic: Dict[str, Any] = {}
                traffic_err = ""
                if token:
                    errs: List[str] = []
                    endpoints = [
                        ("views", f"{repo_url}/traffic/views?per=day"),
                        ("clones", f"{repo_url}/traffic/clones?per=day"),
                        ("referrers", f"{repo_url}/traffic/popular/referrers"),
                        ("paths", f"{repo_url}/traffic/popular/paths"),
                    ]
                    for key, url in endpoints:
                        try:
                            traffic[key] = client.get_json(url)
                        except Exception as e:
                            errs.append(f"{key}: {_safe_str(str(e), 800)}")
                    traffic_err = "\n".join(errs).strip()

                out["repos"].append({
                    "repo": full,
                    "html_url": _safe_str(repo.get("html_url") or "", 256),
                    "default_branch": _safe_str(repo.get("default_branch") or "", 128),
                    "pushed_at": _safe_str(repo.get("pushed_at") or "", 64),
                    "updated_at": _safe_str(repo.get("updated_at") or "", 64),
                    "created_at": _safe_str(repo.get("created_at") or "", 64),
                    "commits_total": int(commits_total),
                    "commits_error": commits_err,
                    # extra computed totals (robust)
                    "views_14d_total": _traffic_total_from_series(traffic.get("views"), "views") if traffic else 0,
                    "clones_14d_total": _traffic_total_from_series(traffic.get("clones"), "clones") if traffic else 0,
                    "stars": _clamp_int(repo.get("stargazers_count"), 0, 2_000_000_000, 0),
                    "forks": _clamp_int(repo.get("forks_count"), 0, 2_000_000_000, 0),
                    "watchers": _clamp_int(repo.get("subscribers_count"), 0, 2_000_000_000, 0),
                    "open_issues": _clamp_int(repo.get("open_issues_count"), 0, 2_000_000_000, 0),

                    "size_kb": _clamp_int(repo.get("size"), 0, 2_000_000_000, 0),
                    "language": _safe_str(repo.get("language") or "", 64),
                    "languages": langs if isinstance(langs, dict) else {},

                    "releases_count": len(releases),
                    "release_asset_downloads_total": int(total_asset_downloads),
                    "releases": per_release,

                    "traffic": traffic,
                    "traffic_error": traffic_err,
                })

                meta["count"] += 1

            except Exception as e:
                out["errors"].append({"repo": full, "error": _safe_str(str(e), 4000)})

        return out, meta


@block("github_aggregate")
@dataclass
class GitHubAggregateBlock(BaseBlock):
    """
    Aggregate totals across repos.
    Input: output from github_fetch
    Output: same dict plus "totals"
    """
    def execute(self, payload: Any, *, params: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        payload = payload if isinstance(payload, dict) else {}
        repos = payload.get("repos") or []
        totals = {
            "repos": 0,
            "stars": 0,
            "forks": 0,
            "watchers": 0,
            "open_issues": 0,
            "release_asset_downloads_total": 0,
            "views_14d_total": 0,
            "views_14d_unique": 0,
            "clones_14d_total": 0,
            "clones_14d_unique": 0,
            "commits_total": 0,
        }

        for r in repos:
            if not isinstance(r, dict):
                continue
            totals["repos"] += 1
            totals["stars"] += _clamp_int(r.get("stars"), 0, 2_000_000_000, 0)
            totals["forks"] += _clamp_int(r.get("forks"), 0, 2_000_000_000, 0)
            totals["watchers"] += _clamp_int(r.get("watchers"), 0, 2_000_000_000, 0)
            totals["open_issues"] += _clamp_int(r.get("open_issues"), 0, 2_000_000_000, 0)
            totals["release_asset_downloads_total"] += _clamp_int(r.get("release_asset_downloads_total"), 0, 2_000_000_000, 0)

            traffic = r.get("traffic") if isinstance(r.get("traffic"), dict) else {}
            views = traffic.get("views") if isinstance(traffic.get("views"), dict) else {}
            clones = traffic.get("clones") if isinstance(traffic.get("clones"), dict) else {}

            totals["views_14d_total"] += _clamp_int(views.get("count"), 0, 2_000_000_000, 0)
            totals["views_14d_unique"] += _clamp_int(views.get("uniques"), 0, 2_000_000_000, 0)
            totals["clones_14d_total"] += _clamp_int(clones.get("count"), 0, 2_000_000_000, 0)
            totals["clones_14d_unique"] += _clamp_int(clones.get("uniques"), 0, 2_000_000_000, 0)
            totals["commits_total"] += _clamp_int(r.get("commits_total"), 0, 2_000_000_000, 0)
        payload["totals"] = totals
        return payload, {"ok": True}
