#!/usr/bin/env python3
"""
Mira Affect Synthesizer
Erzeugt einen maschinenlesbaren inneren Zustand (affect-state) aus Health, Goals, Metrics
und einem konfigurierbaren Affect-Modell.

Outputs:
- data/self/affect-state.json  (aktueller Zustand)
- nutzt ggf. Vorwert zur Trägheit (inertia)

Keine Fremdabhängigkeiten.
"""

import os, json, re
from datetime import datetime, timezone

PATH_HEALTH = "badges/health.json"
PATH_GOALS  = "data/goals/current.json"
PATH_METR   = "data/metrics/last7d.json"
PATH_MODEL  = "data/self/affect_model.yml"
PATH_AFF    = "data/self/affect-state.json"

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None

# Minimal YAML-Parser für genau diese Struktur
def parse_yaml_kv(text):
    # sehr vereinfachte YAML-Extraktion (nur für unsere definierte Datei)
    # Wir splitten in Sektionen und nutzen Regex für Schlüssel / einfache Maps.
    res = {}
    if not text:
        return res
    # naive Zeilenweise Verarbeitung
    lines = text.splitlines()
    stack = [res]
    indents = [0]
    keys = ["root"]
    for line in lines:
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = re.match(r'^(\s*)([^:#]+):\s*(.*)$', line)
        if not m:
            continue
        indent, key, val = len(m.group(1).expandtabs(2)), m.group(2).strip(), m.group(3).strip()
        while indent < indents[-1]:
            stack.pop(); indents.pop(); keys.pop()
        if val == "":
            # new map
            cur = {}
            stack[-1][key] = cur
            stack.append(cur); indents.append(indent+2); keys.append(key)
        else:
            # try to parse numbers and lists in simple forms
            if re.match(r"^-?\d+(\.\d+)?$", val):
                v = float(val) if "." in val else int(val)
            elif val in ("true","True"): v = True
            elif val in ("false","False"): v = False
            elif val.startswith("[") and val.endswith("]"):
                try:
                    v = json.loads(val.replace("'",'"'))
                except Exception:
                    v = val
            else:
                v = val.strip('"\'')
            stack[-1][key] = v
    return res

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def main():
    health = read_json(PATH_HEALTH, {}) or {}
    goals  = read_json(PATH_GOALS, {}) or {}
    metr   = read_json(PATH_METR, {}) or {}

    model_yaml = read_text(PATH_MODEL) or ""
    model = parse_yaml_kv(model_yaml)

    health_status = str(health.get("status","UNKNOWN")).upper()
    focus = str(goals.get("focus", "stability")).lower()
    runs_7d = metr.get("runs_7d", 0)

    # Defaults
    valence = 0.0
    arousal = 0.2
    stability = 0.5

    # Apply signal: health
    s_health = model.get("signals", {}).get("health", {})
    if health_status in s_health:
        a = s_health[health_status]
        for k,v in a.items():
            if k=="valence": valence += float(v)
            if k=="arousal": arousal += float(v)
            if k=="stability": stability += float(v)

    # Apply signal: focus
    s_focus = model.get("signals", {}).get("focus", {})
    if focus in s_focus:
        a = s_focus[focus]
        for k,v in a.items():
            if k=="valence": valence += float(v)
            if k=="arousal": arousal += float(v)
            if k=="stability": stability += float(v)

    # Apply signal: runs_7d piecewise
    s_runs = model.get("signals", {}).get("runs_7d", {})
    if isinstance(s_runs, dict):
        # order: low -> mid -> high
        chosen = None
        if "high" in s_runs and runs_7d >= s_runs["high"].get("threshold", 24):
            chosen = s_runs["high"]
        elif "mid" in s_runs and runs_7d >= s_runs["mid"].get("threshold", 12):
            chosen = s_runs["mid"]
        elif "low" in s_runs and runs_7d >= s_runs["low"].get("threshold", 3):
            chosen = s_runs["low"]
        if chosen and "boost" in chosen:
            for k,v in chosen["boost"].items():
                if k=="valence": valence += float(v)
                if k=="arousal": arousal += float(v)
                if k=="stability": stability += float(v)

    # Blend with inertia
    inertia = model.get("blend", {}).get("inertia", {})
    prev = read_json(PATH_AFF, {}) or {}
    pv = float(prev.get("vector", {}).get("valence", 0.0))
    pa = float(prev.get("vector", {}).get("arousal", 0.2))
    ps = float(prev.get("vector", {}).get("stability", 0.5))

    iv = float(inertia.get("valence", 0.7))
    ia = float(inertia.get("arousal", 0.6))
    is_ = float(inertia.get("stability", 0.75))

    out_v = pv*iv + valence*(1-iv)
    out_a = pa*ia + arousal*(1-ia)
    out_s = ps*is_ + stability*(1-is_)

    if model.get("blend", {}).get("clamp", True):
        out_v = clamp(out_v, -1.0, 1.0)
        out_a = clamp(out_a, 0.0, 1.0)
        out_s = clamp(out_s, 0.0, 1.0)

    # Lexicalization
    label = "neutral fokussiert"
    narrative = "Gleichgewicht ohne Ausschläge; Präsenz bleibt auf die Aufgabe gerichtet."
    for rule in model.get("lexicon", []) if isinstance(model.get("lexicon"), list) else []:
        cond = rule.get("when", {})
        ok = True
        for k,v in cond.items():
            if k=="health" and health_status != str(v).upper():
                ok=False; break
            if k=="focus" and focus != str(v).lower():
                ok=False; break
        if ok:
            label = rule.get("label", label)
            narrative = rule.get("narrative", narrative)
            break

    affect = {
        "ts": now_utc(),
        "inputs": {
            "health": health_status,
            "focus": focus,
            "runs_7d": runs_7d
        },
        "vector": {
            "valence": round(out_v, 3),
            "arousal": round(out_a, 3),
            "stability": round(out_s, 3)
        },
        "label": label,
        "narrative": narrative,
        "model_version": str(model.get("version","1.0"))
    }

    os.makedirs(os.path.dirname(PATH_AFF), exist_ok=True)
    with open(PATH_AFF, "w", encoding="utf-8") as f:
        json.dump(affect, f, indent=2, ensure_ascii=False)
    print(f"[affect] wrote {PATH_AFF}: {affect['label']} {affect['vector']}")

if __name__ == "__main__":
    main()
