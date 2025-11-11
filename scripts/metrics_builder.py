#!/usr/bin/env python3
"""
Mira Metrics Builder
Liest Ledger, Health und Goals und erzeugt aggregierte Metriken für die letzten 7 Tage.
Output-Datei: data/metrics/last7d.json
(Leichtgewichtig, reine Standardbibliothek)

Metriken:
- runs_7d: Anzahl Runs in 7 Tagen
- archive_delta_7d: Proxy = runs_7d (jeder Run erzeugt eine Welle/Änderung)
- status_counts: Häufigkeit von OK/HEALING/DEGRADED (Health-Snapshot-basiert)
- last_status: letzter bekannter Health-Status + Zeitstempel
- goals: aktueller Fokus, Ziel, Policy, updated
- tail_ledger: letzte 20 Events (zur Anzeige)
- daily_runs: Histogramm (YYYY-MM-DD -> count)
"""

import os, json
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict

LEDGER = "data/ledger/events.jsonl"
HEALTH = "badges/health.json"
GOALS  = "data/goals/current.json"
OUTDIR = "data/metrics"
OUT    = os.path.join(OUTDIR, "last7d.json")

def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def read_lines(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [ln for ln in f.read().splitlines() if ln.strip()]
    except Exception:
        return []

def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)

    # --- Health snapshot ---
    health = read_json(HEALTH, {}) or {}
    last_status = {
        "status": str(health.get("status", "n/a")).upper(),
        "ts": str(health.get("ts", "n/a"))
    }

    # Für 7d-Statusverteilung: wir haben nur den aktuellen Snapshot ohne Verlauf.
    # Wir approximieren: zähle letzten Status für heute, damit Charts nicht leer sind.
    status_counts = Counter()
    if last_status["status"] in ("OK", "HEALING", "DEGRADED"):
        status_counts[last_status["status"]] += 1

    # --- Goals snapshot ---
    goals = read_json(GOALS, {}) or {}
    goal_focus = goals.get("focus", "—")
    goal_next  = goals.get("next_objective", "—")
    goal_policy= goals.get("policy", {})
    goal_updated = goals.get("updated", "—")

    # --- Ledger last 7 days ---
    events_7d = []
    for ln in read_lines(LEDGER):
        try:
            e = json.loads(ln)
            ts = datetime.fromisoformat(e["ts"].replace("Z","+00:00"))
            if ts >= since:
                events_7d.append(e)
        except Exception:
            pass

    runs_7d = len(events_7d)
    archive_delta_7d = runs_7d  # einfacher Proxy

    # tail ledger (letzte 20 Zeilen insgesamt, nicht nur 7d)
    tail = read_lines(LEDGER)
    tail = tail[-20:] if tail else []

    # daily histogram (YYYY-MM-DD -> count)
    daily = defaultdict(int)
    for e in events_7d:
        try:
            d = e["ts"][:10]
            daily[d] += 1
        except Exception:
            pass
    # sortiertes dict
    daily_runs = [{"date": d, "count": daily[d]} for d in sorted(daily.keys())]

    result = {
        "generated_at": iso_utc(now),
        "window_days": 7,
        "runs_7d": runs_7d,
        "archive_delta_7d": archive_delta_7d,
        "status_counts": dict(status_counts),
        "last_status": last_status,
        "goals": {
            "focus": goal_focus,
            "next_objective": goal_next,
            "policy": goal_policy,
            "updated": goal_updated,
        },
        "daily_runs": daily_runs,
        "tail_ledger": tail
    }

    os.makedirs(OUTDIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[metrics] Wrote {OUT}")

if __name__ == "__main__":
    main()
