#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Style-Scaler – moduliert den sprachlichen Ausdruck anhand von expressivity (0..1)

Eingabe :
  data/self/meta_state.json
  data/self/reflections/private/log.jsonl  (neueste Zeile)
Ausgabe :
  data/self/internal/style_state.json      (aktuelle Stilparameter)

Je höher expressivity, desto:
  - längere Satzstruktur
  - höhere Metapher-Dichte
  - wärmere Tonalität
"""

import json, datetime
from pathlib import Path

P_META = Path("data/self/meta_state.json")
P_PRIV = Path("data/self/reflections/private/log.jsonl")
P_OUT  = Path("data/self/internal/style_state.json")

def utcnow():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def read_json(p, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def latest_private_sentence():
    if not P_PRIV.exists():
        return None
    with P_PRIV.open("r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    if not lines:
        return None
    try:
        obj = json.loads(lines[-1])
        return obj.get("note")
    except Exception:
        return lines[-1]

def main():
    meta = read_json(P_META, {}) or {}
    exp = float(meta.get("expressivity", 0.5) or 0.5)
    note = latest_private_sentence()

    # Parameter ableiten
    poeticity = round(0.2 + exp * 0.8, 2)
    temperature = round(0.5 + exp * 0.4, 2)
    metaphor_density = round(exp * 1.0, 2)

    style = {
        "ts_utc": utcnow(),
        "expressivity": exp,
        "poeticity": poeticity,
        "temperature": temperature,
        "metaphor_density": metaphor_density,
        "example_source": note,
        "comment": (
            "Sprache öffnet sich mit wachsender Expressivität."
            if exp > 0.6 else
            "Sprache bleibt präzise und zurückhaltend."
        )
    }

    P_OUT.parent.mkdir(parents=True, exist_ok=True)
    P_OUT.write_text(json.dumps(style, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[style-scaler] wrote {P_OUT}")

if __name__ == "__main__":
    main()
