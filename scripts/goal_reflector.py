#!/usr/bin/env python3
"""
Mira Goal Reflector
Analysiert Ledger + Health, berechnet neue Zielzustände (teleologische Anpassung)
und aktualisiert data/goals/current.json im Einklang mit data/goals/schema.json
"""

import json, os, time, statistics
from datetime import datetime, timedelta

LEDGER = "data/ledger/events.jsonl"
HEALTH = "badges/health.json"
GOAL_CURRENT = "data/goals/current.json"

def now():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def safe_load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def load_ledger_events(limit_hours=24):
    """Liest letzte 24h Ledger-Einträge"""
    if not os.path.exists(LEDGER):
        return []
    lines = []
    cutoff = datetime.utcnow() - timedelta(hours=limit_hours)
    with open(LEDGER, "r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
                ts = datetime.fromisoformat(e["ts"].replace("Z",""))
                if ts >= cutoff:
                    lines.append(e)
            except Exception:
                continue
    return lines

def compute_signals(events, health):
    """Erzeuge einfache Metriken aus Ledger + Health"""
    healing_streak = 0
    ok_count = 0
    total = len(events)
    for e in events[-10:]:
        if health.get("status","").upper() == "HEALING":
            healing_streak += 1
    if total > 0:
        ok_count = sum(1 for _ in events if health.get("status","") == "OK")
        ok_ratio_24h = ok_count / total
    else:
        ok_ratio_24h = 1.0
    archive_delta_24h = total  # einfacher Proxy: neue Einträge ~ neue Archivierungen
    return dict(healing_streak=healing_streak, ok_ratio_24h=ok_ratio_24h, archive_delta_24h=archive_delta_24h)

def reflect_goal(current, signals):
    """Teleologische Regelmatrix"""
    focus = current.get("focus", "stability")
    reasoning = "Continuing stable operation."

    # Schwellenwerte
    if signals["healing_streak"] >= 3:
        focus = "resilience"
        reasoning = "Detected consecutive healing events → focus shifts to resilience."
    elif signals["ok_ratio_24h"] > 0.95 and signals["archive_delta_24h"] > 10:
        focus = "growth"
        reasoning = "System stable and productive → focus shifts to growth."
    elif signals["ok_ratio_24h"] < 0.7:
        focus = "stability"
        reasoning = "Low OK ratio → refocus on stability."

    # neue Policy basierend auf Fokus
    policy = dict(current["policy"])
    if focus == "resilience":
        policy["heal_interval_minutes"] = max(30, policy["heal_interval_minutes"] - 10)
        policy["log_verbosity"] = "high"
    elif focus == "growth":
        policy["archive_target_per_day"] = min(48, policy["archive_target_per_day"] + 8)
        policy["log_verbosity"] = "normal"
    elif focus == "stability":
        policy["heal_interval_minutes"] = 60
        policy["log_verbosity"] = "low"

    next_objective = {
        "stability": "maintain steady pulse and reduce heal frequency",
        "growth": "increase archive throughput and enhance reflectivity",
        "resilience": "shorten heal loop and improve error tolerance"
    }[focus]

    new_goal = {
        "version": current.get("version","1.0.0"),
        "updated": now(),
        "focus": focus,
        "next_objective": next_objective,
        "policy": policy,
        "signals": signals,
        "reasoning": reasoning
    }
    return new_goal

def main():
    current = safe_load_json(GOAL_CURRENT, {})
    health = safe_load_json(HEALTH, {})
    events = load_ledger_events()
    signals = compute_signals(events, health)
    new_goal = reflect_goal(current, signals)

    os.makedirs(os.path.dirname(GOAL_CURRENT), exist_ok=True)
    with open(GOAL_CURRENT, "w", encoding="utf-8") as f:
        json.dump(new_goal, f, indent=2)
    print(f"[goal_reflector] Updated goals at {new_goal['updated']} → focus={new_goal['focus']}")

if __name__ == "__main__":
    main()
