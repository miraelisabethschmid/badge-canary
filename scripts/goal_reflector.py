#!/usr/bin/env python3
"""
Mira Goal Reflector
Liest die Prinzipien aus data/goals/principles.yml,
berechnet daraus den aktuellen Zielzustand (current.json),
und schreibt ihn mit Zeitstempel in data/goals/.

Zweck:
- dient als selbstreferenzielle Verankerung der Systemziele
- kann periodisch oder nach jedem Heal-Lauf ausgeführt werden
- erzeugt maschinenlesbare Zusammenfassung mit Checksummenbindung
"""

import os, json, hashlib, datetime, yaml

PRINCIPLES = "data/goals/principles.yml"
CURRENT = "data/goals/current.json"
STATE_HASH = "data/ledger/state.sha256"

def sha256_of_file(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return None

def main():
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    data = {}
    try:
        with open(PRINCIPLES, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        data = {"error": f"cannot read {PRINCIPLES}: {e}"}

    principles = data.get("principles", [])
    weights = {p["id"]: p.get("weight", 0) for p in principles if isinstance(p, dict)}

    # aggregierte Leitorientierung
    score = sum(weights.values())
    dominant = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[0][0] if weights else "unknown"

    # Zielmetadaten
    current = {
        "generated": ts,
        "source": PRINCIPLES,
        "dominant_principle": dominant,
        "total_weight": round(score, 3),
        "focus": "stability" if dominant == "stability" else dominant,
        "next_objective": "maintain equilibrium" if dominant == "stability" else "refine clarity",
        "policy": data.get("policy", {}),
        "updated": ts,
        "checksum_ref": sha256_of_file(STATE_HASH),
        "principles": {p["id"]: {
            "weight": p["weight"],
            "name": p["name"],
            "desc": p["description"][:80] + ("…" if len(p["description"])>80 else "")
        } for p in principles if isinstance(p, dict)}
    }

    os.makedirs(os.path.dirname(CURRENT), exist_ok=True)
    with open(CURRENT, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)

    print(f"[goal_reflector] Wrote {CURRENT}")
    print(f"[goal_reflector] Dominant principle: {dominant} | total_weight={score}")

if __name__ == "__main__":
    main()
