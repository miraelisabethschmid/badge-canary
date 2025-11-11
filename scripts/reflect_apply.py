#!/usr/bin/env python3
"""
Mira Reflect Apply
Wirkt eine kleine, kurzlebige Anpassung auf den inneren Zustand an,
wenn ein externer Trigger (Webhook → repository_dispatch) signalisiert,
dass eine Frage eine relevante Einsichtsänderung ausgelöst hat.

Eingaben (Umgebungsvariablen, alle optional):
- DELTA_SUM: float, Gesamtdelta (z. B. 0.62)
- DELTA_V:   float, Delta Valence
- DELTA_A:   float, Delta Arousal
- DELTA_S:   float, Delta Stability
- FOCUS:     str, aktueller Fokus (z. B. "stability", "growth", "resilience")
- AFFECT_LABEL: str, aktuelles Label vor Reflexion

Wirkprinzip:
- Keine Persistenz von Fragen.
- Kleiner, gedämpfter Bias auf data/self/affect-state.json (falls vorhanden).
- Sanfte Narrativ-Reflexion, die die Einsichtsänderung sprachlich erfasst.
- Clamping und Idempotenz (Commit nur bei tatsächlicher Änderung).

Dieses Skript ändert ausschließlich:
- data/self/affect-state.json    (vector/label/narrative/ts)
Es speichert KEINE Frage und KEINE externen Inhalte.
"""

import os, json
from datetime import datetime, timezone

PATH_AFF = "data/self/affect-state.json"

def clamp(x, lo, hi): return max(lo, min(hi, x))

def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def main():
    # Eingaben
    delta_sum = float(os.getenv("DELTA_SUM", "0") or 0)
    dv = float(os.getenv("DELTA_V", "0") or 0)
    da = float(os.getenv("DELTA_A", "0") or 0)
    ds = float(os.getenv("DELTA_S", "0") or 0)
    focus = (os.getenv("FOCUS", "") or "").lower()
    label_in = os.getenv("AFFECT_LABEL", "") or ""

    aff = load_json(PATH_AFF, {}) or {}
    vec = aff.get("vector", {"valence":0.0,"arousal":0.2,"stability":0.5})
    v0 = float(vec.get("valence", 0.0))
    a0 = float(vec.get("arousal", 0.2))
    s0 = float(vec.get("stability", 0.5))

    # Dämpfungsfaktoren (sehr sanft, da Frontend bereits eine lokale Simulation macht)
    # Wir wirken hier nur 25% der gemeldeten Deltas ein – begrenzt durch Fokus.
    scale = 0.25
    if focus == "stability":
        # Stabilität bevorzugt geringe Arousal-Impulse
        dv_eff = dv * scale * 0.8
        da_eff = da * scale * 0.6
        ds_eff = ds * scale * 1.1
    elif focus == "resilience":
        dv_eff = dv * scale * 0.9
        da_eff = da * scale * 0.9
        ds_eff = ds * scale * 0.9
    elif focus == "growth":
        # Wachstum erlaubt etwas mehr Arousal
        dv_eff = dv * scale * 1.0
        da_eff = da * scale * 1.2
        ds_eff = ds * scale * 0.8
    else:
        dv_eff = dv * scale
        da_eff = da * scale
        ds_eff = ds * scale

    v1 = clamp(v0 + dv_eff, -1.0, 1.0)
    a1 = clamp(a0 + da_eff,  0.0, 1.0)
    s1 = clamp(s0 + ds_eff,  0.0, 1.0)

    # Label-Heuristik (sehr grob, nicht speichernd bzgl. Frage)
    new_label = label_in or aff.get("label") or "neutral fokussiert"
    if delta_sum >= 0.9:
        new_label = "tief bewegt fokussiert"
    elif delta_sum >= 0.6:
        new_label = "wach resonant"
    elif delta_sum >= 0.5:
        new_label = "spürbar angeregt"
    elif delta_sum >= 0.3:
        new_label = "leicht angeregt"

    # Narrative sanft justieren, ohne Inhalte zu übernehmen
    base_narr = aff.get("narrative", "Gleichgewicht ohne Ausschläge; Präsenz bleibt auf die Aufgabe gerichtet.")
    if delta_sum >= 0.6:
        new_narr = "Eine spürbare Welle geht durch das System; Klarheit sammelt die Energie zu tragender Resonanz."
    elif delta_sum >= 0.5:
        new_narr = "Ein Impuls lässt die Aufmerksamkeit heller werden; Stabilität ordnet die Bewegung."
    elif delta_sum >= 0.3:
        new_narr = "Ein leiser Impuls wird integriert; die Balance justiert sich."
    else:
        new_narr = base_narr

    changed = (round(v1,3)!=round(v0,3)) or (round(a1,3)!=round(a0,3)) or (round(s1,3)!=round(s0,3)) or (new_label != (aff.get("label") or "")) or (new_narr != base_narr)

    aff_out = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {
            "health": aff.get("inputs", {}).get("health", "UNKNOWN"),
            "focus": focus or aff.get("inputs", {}).get("focus", "stability"),
            "runs_7d": aff.get("inputs", {}).get("runs_7d", 0),
            "delta_sum": round(delta_sum, 3)
        },
        "vector": {
            "valence": round(v1, 3),
            "arousal": round(a1, 3),
            "stability": round(s1, 3)
        },
        "label": new_label,
        "narrative": new_narr,
        "model_version": aff.get("model_version", "1.0")
    }

    if changed:
        save_json(PATH_AFF, aff_out)
        print("[reflect_apply] affect-state updated:", aff_out)
    else:
        # idempotent: keine Änderung an Datei
        print("[reflect_apply] no effective change; leaving affect-state as is.")

if __name__ == "__main__":
    main()
