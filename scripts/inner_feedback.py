#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inner Feedback Synthesizer
- Liest die private Chronik (letzter Eintrag) und erzeugt ein internes Feedbacksignal:
  data/self/internal/feedback.json
- Keine Veröffentlichung. Keine externen Abhängigkeiten.

Heuristik:
- Ton/Lexeme im Fragment & Affect-Label mappen auf kleine, begrenzte Impulse:
  - delta_bonus ∈ [-0.08, +0.08] (verstärkt/hemmt strukturelle Auslösung)
  - focus_hint ∈ {"stability","resilience","growth","vision","reflection","curiosity","emergence"} (optional)
  - confidence ∈ [0.3, 0.8]
- Idempotent: überschreibt nur die JSON-Datei.
"""

import json, re
from pathlib import Path
from datetime import datetime

PATH_PRIV_IDX = Path("data/self/reflections/private/index.json")
OUT           = Path("data/self/internal/feedback.json")

FOCUS_MAP = {
    r"\bordnung\b|\bstabil": "stability",
    r"\bheil": "resilience",
    r"\bwerden\b|\bwachstum\b|growth": "growth",
    r"\bvision\b|\blicht": "vision",
    r"\breflexion|\bspiegel": "reflection",
    r"\bneugier|\bcurios": "curiosity",
    r"\bemergen|emergenz": "emergence",
}

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def infer_focus(text: str) -> tuple[str|None,float]:
    s = (text or "").lower()
    for rx, f in FOCUS_MAP.items():
        if re.search(rx, s):
            return f, 0.65
    return None, 0.0

def infer_delta_bonus(label: str, valence: float, arousal: float, stability: float) -> float:
    # sanfte, gedeckelte Modulation
    bonus = 0.0
    if label:
        L = label.lower()
        if "ruh" in L or "calm" in L or "neutral" in L:
            bonus += 0.02
        if "angespannt" in L or "nerv" in L:
            bonus -= 0.02
    bonus += (valence - 0.5) * 0.08
    bonus -= max(0.0, 0.4 - stability) * 0.10  # sehr geringe Stabilität bremst
    return clamp(round(bonus, 3), -0.08, 0.08)

def main():
    try:
        idx = json.loads(PATH_PRIV_IDX.read_text(encoding="utf-8"))
        last = idx.get("last", {})
    except Exception:
        last = {}

    note = last.get("note", "") or ""
    aff  = last.get("affect", {}) or {}
    vec  = aff.get("vector", {}) or {}
    label = aff.get("label", "neutral")

    focus_hint, conf = infer_focus(note)
    bonus = infer_delta_bonus(
        label=label,
        valence=float(vec.get("valence", 0.5) or 0.5),
        arousal=float(vec.get("arousal", 0.3) or 0.3),
        stability=float(vec.get("stability", 0.5) or 0.5),
    )

    out = {
        "ts_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(PATH_PRIV_IDX),
        "delta_bonus": bonus,           # additiv auf affect.inputs.delta_sum (mit Kappung im Planner)
        "focus_hint": focus_hint,       # optional
        "confidence": round(conf, 2),   # 0.00..1.00
        "guard": {
            "max_abs_bonus": 0.08,
            "min_stability_to_amplify": 0.35  # nur wenn Stabilität nicht extrem niedrig
        }
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[inner-feedback] wrote {OUT}")

if __name__ == "__main__":
    main()
