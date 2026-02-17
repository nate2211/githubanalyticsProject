# main.py
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict

import blocks  # registers BLOCKS
from blocks import app_dir, load_json, save_json
from gui import run_gui, run_block


def run_cli(repos: list[str], token: str) -> int:
    payload = {"repos": repos, "token": token}
    data, _m1 = run_block("github_fetch", payload, {})
    data, _m2 = run_block("github_aggregate", data, {})

    print(json.dumps(data.get("totals", {}), indent=2))
    out_path = app_dir() / "analytics_cli.json"
    save_json(out_path, data)
    print(f"\nSaved full report to: {out_path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="githubanalyticsProject")
    ap.add_argument("--cli", action="store_true", help="Run in CLI mode (no GUI)")
    ap.add_argument("--repos", nargs="*", default=[], help="Repos like owner/name")
    ap.add_argument("--token", default="", help="GitHub token (or set env GITHUB_TOKEN)")
    args = ap.parse_args()

    if not args.cli:
        run_gui()
        return 0

    token = (args.token or "").strip() or (os.environ.get("GITHUB_TOKEN") or "").strip()
    repos = args.repos
    if not repos:
        cfg = load_json(app_dir() / "config.json", default={})
        repos = cfg.get("repos") or []
        repos = [str(x) for x in repos if x]

    if not repos:
        print("No repos provided. Use --repos owner/name ... or put repos in ~/.githubanalyticsProject/config.json")
        return 2

    return run_cli(repos, token)


if __name__ == "__main__":
    raise SystemExit(main())
