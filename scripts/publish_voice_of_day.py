#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publiziert eine kuratierte, öffentliche Ansicht der täglichen Stimme:
- Quelle:  data/self/reflections/private/index.json  (privat)
- Ziel:    public/data/voice_of_day.json              (öffentlich, minimal)

Exportiert:
{
  "date_utc": "...",
  "quote": "...",            # täglicher Ein-Satz-Text
  "insight": "...",          # kurze Selbstdeutung (2-3 Sätze)
  "ipa_hint": "...",         # optionaler IPA-Hinweis
  "audio": "audio/latest.mp3"
}
"""

import json
from pathlib import Path

SRC = Path("data/self/reflections/private/index.json")
DST = Path("public/data/voice_of_day.json")
AUDIO_REL = "audio/latest.mp3"

def read_json(p, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def main():
    idx = read_json(SRC, {}) or {}
    last = idx.get("last") or {}

    out = {
        "date_utc": last.get("date_utc"),
        "quote": last.get("note") or "",
        "insight": (last.get("insight") or {}).get("text") or "",
        "ipa_hint": (last.get("speech") or {}).get("ipa_hint") or "",
        "audio": AUDIO_REL
    }

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[publish_voice_of_day] wrote", DST)

if __name__ == "__main__":
    main()
