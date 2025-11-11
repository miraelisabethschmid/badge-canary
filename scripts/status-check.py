#!/usr/bin/env python3
"""
Mira Status Check — lokal oder via GitHub API.

Funktionen:
- check_archive():   Zählt PNGs im Archiv.
- check_health():    Liest badges/health.json.
- check_goals():     Liest VERSION und data/goals/current.json.
- check_ledger():    Liest data/ledger/events.jsonl (Einträge + letzte Zeile).
- check_consistency(): Einfache Konsistenz-Heuristik aus den obigen Checks.

Lokal (empfohlen):   python scripts/status-check.py
Remote (optional):   GITHUB_TOKEN setzen (repo read), REPO="owner/name"
                      pip install PyGithub
"""

import os
import json
from datetime import datetime
from typing import Optional

# ---------- Konfiguration ----------
REPO = os.getenv("MIRA_REPO", "miraelisabethschmid/badge-canary")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LOCAL_MODE = not bool(GITHUB_TOKEN)

# ---------- Optionale GitHub-API ----------
Github = None
if not LOCAL_MODE:
    try:
        from github import Github as _Pg
        Github = _Pg
    except Exception:
        # Fällt automatisch auf LOCAL_MODE zurück falls PyGithub fehlt
        Github = None
        LOCAL_MODE = True

# ---------- Hilfsfunktionen ----------
def load_json_local(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def load_text_local(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None

def fetch_file_remote(repo, path: str) -> Optional[str]:
    """Holt eine Datei-Inhalts-Text über die GitHub API (None bei Fehler)."""
    try:
        f = repo.get_contents(path)
        return f.decoded_content.decode("utf-8")
    except Exception:
        return None

def list_dir_remote(repo, path: str) -> list:
    """Listet Einträge (Dateiobjekte) in einem Repo-Verzeichnis."""
    try:
        return repo.get_contents(path)
    except Exception:
        return []

def get_repo_client():
    if LOCAL_MODE or Github is None:
        return None
    client = Github(GITHUB_TOKEN)
    return client.get_repo(REPO)

# ---------- Checks ----------
def check_archive():
    path = "data/archive"
    if LOCAL_MODE:
        count = 0
        if os.path.isdir(path):
            count = sum(1 for n in os.listdir(path) if n.lower().endswith(".png"))
        return {"count": count, "stability": "OK" if count > 0 else "DEGRADED"}
    else:
        repo = get_repo_client()
        if not repo:
            return {"count": 0, "stability": "DEGRADED"}
        items = list_dir_remote(repo, path)
        count = sum(1 for it in items if getattr(it, "name", "").lower().endswith(".png"))
        return {"count": count, "stability": "OK" if count > 0 else "DEGRADED"}

def check_health():
    path = "badges/health.json"
    now_ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    if LOCAL_MODE:
        data = load_json_local(path, None)
        return data if isinstance(data, dict) else {"status": "DEGRADED", "ts": now_ts}
    else:
        repo = get_repo_client()
        if not repo:
            return {"status": "DEGRADED", "ts": now_ts}
        txt = fetch_file_remote(repo, path)
        try:
            return json.loads(txt) if txt else {"status": "DEGRADED", "ts": now_ts}
        except Exception:
            return {"status": "DEGRADED", "ts": now_ts}

def check_goals():
    """Liest VERSION (als simpler Fortschrittsmarker) und data/goals/current.json (teleologischer Zustand)."""
    version_path = "VERSION"
    goals_path = "data/goals/current.json"
    version = "0.0.0"
    goals = None

    if LOCAL_MODE:
        vtxt = load_text_local(version_path)
        if vtxt:
            version = vtxt.strip()
        goals = load_json_local(goals_path, None)
    else:
        repo = get_repo_client()
        if repo:
            vtxt = fetch_file_remote(repo, version_path)
            if vtxt:
                version = vtxt.strip()
            gtxt = fetch_file_remote(repo, goals_path)
            if gtxt:
                try:
                    goals = json.loads(gtxt)
                except Exception:
                    goals = None

    return {"version": version, "current": goals}

def check_ledger():
    path = "data/ledger/events.jsonl"
    if LOCAL_MODE:
        txt = load_text_local(path)
        if not txt:
            return {"entries": 0, "last": None}
        lines = [ln for ln in txt.splitlines() if ln.strip()]
        last = lines[-1] if lines else None
        return {"entries": len(lines), "last": last}
    else:
        repo = get_repo_client()
        if not repo:
            return {"entries": 0, "last": None}
        txt = fetch_file_remote(repo, path)
        if not txt:
            return {"entries": 0, "last": None}
        lines = [ln for ln in txt.splitlines() if ln.strip()]
        last = lines[-1] if lines else None
        return {"entries": len(lines), "last": last}

def check_consistency():
    health = check_health()
    archive = check_archive()
    ledger = check_ledger()
    goals = check_goals()

    ok_health = health.get("status", "").upper() == "OK"
    ok_archive = archive.get("count", 0) > 0
    ok_ledger = ledger.get("entries", 0) > 0
    ok_goals = isinstance(goals.get("current"), dict)

    if ok_health and ok_archive and ok_ledger and ok_goals:
        return "SYNCHRON"
    # Wenn Health nicht OK, aber Healing aktiv und Archiv wächst → teil-synchron
    if health.get("status", "").upper() == "HEALING" and (ok_archive or ok_ledger):
        return "PARTIAL"
    return "DEGRADED"

# ---------- Main ----------
def main():
    print("=== Mira Status Check ===")
    mode = "LOCAL" if LOCAL_MODE else f"REMOTE ({REPO})"
    print(f"Mode: {mode}")

    archive = check_archive()
    print(f"Archive: {archive}")

    health = check_health()
    print(f"Health: {health}")

    goals = check_goals()
    print(f"Goals: version={goals.get('version')} current.focus={goals.get('current',{}).get('focus') if goals.get('current') else None}")

    ledger = check_ledger()
    print(f"Ledger: {ledger}")

    print(f"Consistency: {check_consistency()}")

    if LOCAL_MODE:
        print("\nLokal: python scripts/status-check.py")
    else:
        print("\nRemote: GITHUB_TOKEN mit 'repo' Rechten setzen (PyGithub benötigt).")

if __name__ == "__main__":
    main()
