#!/usr/bin/env python3
"""
Mira Reflection Logger
Archiviert Änderungen an data/goals/principles.yml als versionsierte "Philosophie"-Snapshots
und protokolliert sie append-only in data/goals/history/index.jsonl.

- Keine externen Abhängigkeiten (nur Standardbibliothek)
- Erzeugt bei Änderung:
  - data/goals/history/principles-<UTC>-<sha256>.yml (vollständiger Snapshot)
  - data/goals/history/diff-<UTC>-<sha256>.patch (Unified-Diff ggü. vorherigem Snapshot)
  - data/goals/history/index.jsonl (eine Zeile pro Änderung mit Metadaten)
  - data/goals/history/latest.json (Zeiger auf den letzten Stand)
"""

import os
import json
import hashlib
from datetime import datetime, timezone
import difflib

PRINCIPLES = "data/goals/principles.yml"
HIST_DIR   = "data/goals/history"
INDEX      = os.path.join(HIST_DIR, "index.jsonl")
LATEST     = os.path.join(HIST_DIR, "latest.json")

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except Exception as e:
        raise RuntimeError(f"cannot read {path}: {e}")

def sha256_text(txt: str) -> str:
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def read_last_index_entry() -> dict | None:
    if not os.path.exists(INDEX):
        return None
    try:
        with open(INDEX, "r", encoding="utf-8") as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
        if not lines:
            return None
        return json.loads(lines[-1])
    except Exception:
        return None

def load_previous_snapshot(prev_hash: str) -> str:
    # try to find snapshot by prev_hash
    if not os.path.isdir(HIST_DIR):
        return ""
    try:
        for name in sorted(os.listdir(HIST_DIR)):
            if name.startswith("principles-") and name.endswith(".yml") and prev_hash in name:
                with open(os.path.join(HIST_DIR, name), "r", encoding="utf-8") as f:
                    return f.read()
    except Exception:
        pass
    return ""

def write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    # 0) Vorbedingungen
    ensure_dir(HIST_DIR)
    now = utc_now()

    # 1) Aktuelle Prinzipien lesen
    current_txt = read_text(PRINCIPLES)
    if not current_txt:
        print(f"[reflection] {PRINCIPLES} not found or empty; nothing to archive.")
        return

    current_hash = sha256_text(current_txt)
    last = read_last_index_entry()
    prev_hash = last.get("hash") if last else None

    # 2) Unverändert? => Kein Eintrag
    if prev_hash == current_hash:
        print(f"[reflection] No change in principles.yml (hash={current_hash[:12]}).")
        # Aktualisiere latest.json trotzdem mit Timestamp (Heartbeat)
        latest = {
            "ts": now,
            "hash": current_hash,
            "path": PRINCIPLES,
            "snapshot": None,
            "diff": None,
            "note": "unchanged"
        }
        write_file(LATEST, json.dumps(latest, indent=2))
        return

    # 3) Vorherige Version laden (für Diff)
    prev_txt = load_previous_snapshot(prev_hash) if prev_hash else ""
    diff = difflib.unified_diff(
        prev_txt.splitlines(keepends=True),
        current_txt.splitlines(keepends=True),
        fromfile=f"principles@{(prev_hash or 'none')[:12]}",
        tofile=f"principles@{current_hash[:12]}",
        lineterm=""
    )
    diff_text = "".join(diff)

    # 4) Snapshots persistieren
    snap_name = f"principles-{now}-{current_hash}.yml"
    diff_name = f"diff-{now}-{current_hash}.patch"
    snap_path = os.path.join(HIST_DIR, snap_name)
    diff_path = os.path.join(HIST_DIR, diff_name)

    write_file(snap_path, current_txt)
    write_file(diff_path, diff_text)

    # 5) Index-Eintrag (append-only)
    entry = {
        "ts": now,
        "hash": current_hash,
        "prev_hash": prev_hash,
        "snapshot": snap_name,
        "diff": diff_name,
        "lines_added": diff_text.count("\n+") - 1 if diff_text else 0,
        "lines_removed": diff_text.count("\n-") - 1 if diff_text else 0
    }
    with open(INDEX, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # 6) Latest-Zeiger
    write_file(LATEST, json.dumps({
        "ts": now,
        "hash": current_hash,
        "path": PRINCIPLES,
        "snapshot": snap_name,
        "diff": diff_name
    }, indent=2))

    print(f"[reflection] Archived new principles snapshot: {snap_name}")
    print(f"[reflection] Diff written: {diff_name}")
    if prev_hash:
        print(f"[reflection] prev={prev_hash[:12]} -> curr={current_hash[:12]}")

if __name__ == "__main__":
    main()
