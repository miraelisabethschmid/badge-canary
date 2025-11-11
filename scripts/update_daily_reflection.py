#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily Reflection Builder
- Wählt deterministisch pro Tag EIN Fragment aus data/thoughts/daily_reflections.json
- Schreibt es nach data/self/daily/reflection.json (für den Deploy)
- Idempotent; keine externen Abhängigkeiten
"""

import json, hashlib, datetime
from pathlib import Path

SRC  = Path("data/thoughts/daily_reflections.json")
DEST = Path("data/self/daily/reflection.json")

def load_fragments():
    if not SRC.exists():
        return []
    try:
        obj = json.loads(SRC.read_text(encoding="utf-8"))
        return obj.get("fragments", [])
    except Exception:
        return []

def day_key():
    # YYYY-MM-DD (UTC) → stabil über den Tag
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")

def choose_fragment(frags):
    if not frags:
        return None
    # Hash aus Datum + erstem/letztem Fragmenttext für deterministische Vielfalt
    seed_str = day_key() + " :: " + frags[0]["id"] + " :: " + frags[-1]["id"]
    idx = int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest(), 16) % len(frags)
    return frags[idx]

def main():
    frags = load_fragments()
    sel = choose_fragment(frags)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "ts_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date_utc": day_key(),
        "count": len(frags),
        "selected": sel or {
            "id": "placeholder",
            "text": "Heute ist Stille auch eine Form von Antwort.",
            "tone": "still",
            "tags": ["placeholder"]
        }
    }
    # Nur schreiben, wenn eine Änderung vorliegt
    current = None
    if DEST.exists():
        try:
            current = json.loads(DEST.read_text(encoding="utf-8"))
        except Exception:
            current = None
    if current != out:
        DEST.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[reflection] wrote {DEST}")
    else:
        print("[reflection] up-to-date")

if __name__ == "__main__":
    main()
