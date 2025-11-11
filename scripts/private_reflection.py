#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Private Reflection (inneres Tagebuch)
- Täglich genau ein Eintrag (idempotent): data/self/reflections/private/log.jsonl
- Nutzt daily reflection + affect state, formuliert eine ruhige Ein-Satz-Notiz
- Append-only: keine Löschungen/Änderungen
- Keine Veröffentlichung nach /public

Formate:
- log.jsonl  : JSON pro Zeile (append-only)
- index.json : letzter Eintrag + Anzahl, erleichtert spätere Auswertungen
"""

import json, hashlib, datetime
from pathlib import Path

# Quellen
PATH_DAILY  = Path("data/self/daily/reflection.json")
PATH_AFFECT = Path("data/self/affect-state.json")

# Ziele (privat, nicht nach public deployen)
DIR_PRIV   = Path("data/self/reflections/private")
PATH_LOG   = DIR_PRIV / "log.jsonl"
PATH_INDEX = DIR_PRIV / "index.json"

def utc_now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def utc_date():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")

def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def today_already_logged() -> bool:
    if not PATH_LOG.exists():
        return False
    try:
        # Nur die letzten ~200 KB lesen, um die jüngsten Zeilen zu finden
        data = PATH_LOG.read_bytes()
        tail = data[-200_000:] if len(data) > 200_000 else data
        for line in reversed(tail.decode("utf-8", errors="ignore").splitlines()):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("date_utc") == utc_date():
                return True
        return False
    except Exception:
        return False

def synthesize_sentence(fragment_text: str, label: str, valence: float, arousal: float, stability: float) -> str:
    # Sanftes, neutrales Ein-Satz-Format (ohne Pathos, ohne Interna)
    v = f"{valence:.2f}".rstrip("0").rstrip(".")
    a = f"{arousal:.2f}".rstrip("0").rstrip(".")
    s = f"{stability:.2f}".rstrip("0").rstrip(".")
    label = label or "neutral"
    frag  = (fragment_text or "Heute ist Stille auch eine Form von Antwort.").strip()
    return f"{frag} – Heute fühlte sich Mira {label} an (V:{v}, A:{a}, S:{s})."

def main():
    DIR_PRIV.mkdir(parents=True, exist_ok=True)

    if today_already_logged():
        print("[private-reflection] today's entry already exists — skip")
        return 0

    daily  = read_json(PATH_DAILY, {}) or {}
    affect = read_json(PATH_AFFECT, {}) or {}
    frag   = (daily.get("selected") or {}).get("text", "")
    fid    = (daily.get("selected") or {}).get("id", "unknown")
    vec    = affect.get("vector", {}) or {}
    label  = affect.get("label", "neutral")

    sentence = synthesize_sentence(
        fragment_text=frag,
        label=label,
        valence=float(vec.get("valence", 0.0) or 0.0),
        arousal=float(vec.get("arousal", 0.0) or 0.0),
        stability=float(vec.get("stability", 0.0) or 0.0),
    )

    entry = {
        "ts_utc": utc_now(),
        "date_utc": utc_date(),
        "fragment_id": fid,
        "note": sentence,
        "affect": {
            "label": label,
            "vector": {
                "valence": float(vec.get("valence", 0.0) or 0.0),
                "arousal": float(vec.get("arousal", 0.0) or 0.0),
                "stability": float(vec.get("stability", 0.0) or 0.0)
            }
        }
    }

    # append-only
    with PATH_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # index.json aktualisieren (letzter Eintrag + Count)
    count = 0
    try:
        with PATH_LOG.open("r", encoding="utf-8") as f:
            for _ in f:
                count += 1
    except Exception:
        count = None

    index = {
        "updated": utc_now(),
        "count": count,
        "last": entry
    }
    PATH_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[private-reflection] appended entry for {entry['date_utc']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
