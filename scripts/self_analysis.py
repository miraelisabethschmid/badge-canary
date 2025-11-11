#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira — Autonomous Self-Analysis Loop

Ziel:
- Analysiert stündliche Selbstbilder (Ledger) + aktuellen Affect-State.
- Leitet Trends (24h/7d) ab und erzeugt strukturierte Einsichten.
- Aktualisiert ein leichtes, erklärbares Lernprofil (learning.json),
  das die Render-Abbildung sanft moduliert (z. B. Mimik-Empfindlichkeit).
- Optional: passt self-describe Nuancen minimal an (nur Textbausteine).

Prinzipien:
- Deterministisch pro Lauf, rein lokal, keine externen Aufrufe.
- Idempotent: gleiche Eingaben → gleiche Ausgaben.
- Tamper-evident (SHA256) für insight.json.
"""

import os, json, math, hashlib, statistics as stats
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = datetime.now(timezone.utc)
ROOT = Path(".").resolve()

P_LEDGER = ROOT / "data" / "ledger" / "events.jsonl"
P_AFFECT = ROOT / "data" / "self" / "affect-state.json"
P_LEARN  = ROOT / "data" / "self" / "learning.json"
P_INS    = ROOT / "data" / "self" / "insight.json"
P_SELF   = ROOT / "data" / "self" / "self-describe.json"

# ---------- helpers ----------
def jload(p, default=None):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def read_ledger(path: Path):
    rows = []
    if not path.exists(): return rows
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln: continue
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            # filter only self_image events
            if obj.get("type") != "self_image": continue
            # parse ts
            ts = obj.get("ts")
            try:
                t = datetime.fromisoformat(ts.replace("Z","+00:00"))
            except Exception:
                continue
            rows.append({
                "ts": ts,
                "t": t,
                "val": float(obj.get("valence", 0.0)),
                "aro": float(obj.get("arousal", 0.0)),
                "stab": float(obj.get("stability", 0.0)),
                "label": obj.get("label","neutral")
            })
    rows.sort(key=lambda r: r["t"])  # oldest→newest
    return rows

def window(rows, hours):
    if not rows: return []
    cutoff = UTC - timedelta(hours=hours)
    return [r for r in rows if r["t"] >= cutoff]

def mean(xs, default=0.0):
    xs = [x for x in xs if isinstance(x,(int,float))]
    if not xs: return default
    try:
        return float(stats.fmean(xs))
    except Exception:
        return float(sum(xs)/len(xs))

def stdev(xs, default=0.0):
    xs = [x for x in xs if isinstance(x,(int,float))]
    if len(xs) < 2: return default
    try:
        return float(stats.pstdev(xs))
    except Exception:
        return default

def sha256_str(s: str) -> str:
    h = hashlib.sha256()
    h.update(s.encode("utf-8"))
    return h.hexdigest()

def clamp(x,a,b): 
    return a if x<a else b if x>b else x

# ---------- load data ----------
ledger = read_ledger(P_LEDGER)
aff = jload(P_AFFECT, {"label":"neutral","vector":{"valence":0.0,"arousal":0.3,"stability":0.6},"inputs":{}})
learn = jload(P_LEARN, {
    "version": 1,
    "updated_utc": None,
    "weights": {
        "viseme_mouth_gain": 1.0,      # Basisöffnung
        "sibilant_bias": 0.15,         # Brackets-Sichtbarkeit bei S/FV
        "tempo_affect_gain": 1.0,      # Tempo-Sensitivity
        "exposure_affect_gain": 1.0,   # Belichtungssensitivität
        "contrast_affect_gain": 1.0    # Kontrastsensitivität
    },
    "notes": "Light, bounded adaptations derived from last 24h/7d affect."
})
selfd = jload(P_SELF, {"physical":{"description":"—"},"voice":{"profile":"—"},"affect":{"narrative":"—"}})

# ---------- compute windows ----------
last24 = window(ledger, 24)
last168 = window(ledger, 168)  # 7 Tage

def summarize(rows):
    if not rows:
        return {"n":0,"v_mean":0,"a_mean":0,"s_mean":0,"v_sd":0,"a_sd":0,"s_sd":0,"labels":{}}
    v = [r["val"] for r in rows]
    a = [r["aro"] for r in rows]
    s = [r["stab"] for r in rows]
    lab = {}
    for r in rows:
        lab[r["label"]] = lab.get(r["label"],0) + 1
    return {
        "n": len(rows),
        "v_mean": round(mean(v), 4),
        "a_mean": round(mean(a), 4),
        "s_mean": round(mean(s), 4),
        "v_sd": round(stdev(v), 4),
        "a_sd": round(stdev(a), 4),
        "s_sd": round(stdev(s), 4),
        "labels": lab
    }

s24 = summarize(last24)
s7d = summarize(last168)

# ---------- derive insights ----------
# Trendrichtung (einfacher Vergleich: heutiger Mittelwert vs 7d-Mittel)
trend = {
    "valence": round(s24["v_mean"] - s7d["v_mean"], 4) if s7d["n"] else 0.0,
    "arousal": round(s24["a_mean"] - s7d["a_mean"], 4) if s7d["n"] else 0.0,
    "stability": round(s24["s_mean"] - s7d["s_mean"], 4) if s7d["n"] else 0.0
}

# Qualitätssignale:
# - hohe Arousal-Streuung → Artikulation stabilisieren (Sibilanten leicht erhöhen)
# - niedrige Valenz + hohe Arousal → Mimik beruhigen (Mouth-Gain leicht dämpfen)
# - hohe Stabilität → Exposure/Contrast etwas empfindlicher (mehr Nuancen)
rules = []

if s24["a_sd"] >= 0.15:
    rules.append({"key":"sibilant_bias","+=": 0.03, "why":"Arousal Streuung hoch → Artikulation stabilisieren."})
if s24["v_mean"] < -0.15 and s24["a_mean"] > 0.45:
    rules.append({"key":"viseme_mouth_gain","*=": 0.96, "why":"Niedrige Valenz + hohe Erregung → Öffnung leicht beruhigen."})
if s24["s_mean"] >= 0.70:
    rules.append({"key":"exposure_affect_gain","+=": 0.04, "why":"Hohe Stabilität → feinere Belichtungsnuancen zulassen."})
if s24["s_mean"] >= 0.70 and s24["a_sd"] <= 0.08:
    rules.append({"key":"contrast_affect_gain","+=": 0.03, "why":"Stabil & ruhig → Kontrast feinfühliger modulieren."})
if s24["v_mean"] >= 0.25 and s24["a_mean"] >= 0.45:
    rules.append({"key":"tempo_affect_gain","+=": 0.05, "why":"Helle Aktivität → Tempo minimal lebendiger."})

# ---------- apply bounded updates ----------
weights = learn.get("weights", {}).copy()

def apply_rule(w, r):
    k = r["key"]
    if k not in w: return
    old = float(w[k])
    if "+=" in r:
        new = old + float(r["+="])
    elif "*=" in r:
        new = old * float(r["*="])
    else:
        return
    # bounds per key
    bounds = {
        "viseme_mouth_gain": (0.85, 1.35),
        "sibilant_bias": (0.0, 0.5),
        "tempo_affect_gain": (0.75, 1.35),
        "exposure_affect_gain": (0.8, 1.25),
        "contrast_affect_gain": (0.85, 1.25)
    }
    a,b = bounds.get(k,(0.0,2.0))
    new = clamp(new, a, b)
    w[k] = round(new, 4)

applied = []
for r in rules:
    before = weights.copy()
    apply_rule(weights, r)
    if before != weights:
        applied.append(r)

# ---------- build insight ----------
insight = {
    "ts": UTC.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "windows": {
        "last24h": s24,
        "last7d": s7d
    },
    "trend_vs_7d": trend,
    "affect_now": aff,
    "rules_applied": applied
}
raw = json.dumps(insight, ensure_ascii=False, sort_keys=True)
insight["sha256"] = sha256_str(raw)

# ---------- persist outputs ----------
os.makedirs(P_INS.parent, exist_ok=True)
with open(P_INS, "w", encoding="utf-8") as f:
    json.dump(insight, f, ensure_ascii=False, indent=2)

learn_out = {
    "version": int(learn.get("version",1)),
    "updated_utc": insight["ts"],
    "weights": weights,
    "explain": [r["why"] for r in applied]
}
os.makedirs(P_LEARN.parent, exist_ok=True)
with open(P_LEARN, "w", encoding="utf-8") as f:
    json.dump(learn_out, f, ensure_ascii=False, indent=2)

# ---------- optional: nudge self-describe (tiny, safe) ----------
sd = selfd
narr = (sd.get("affect") or {}).get("narrative","")
prefix = "Ich lerne meine Artikulation zu verfeinern; "
if applied and prefix not in narr:
    sd.setdefault("affect", {}).update({
        "narrative": (prefix + narr)[:600]
    })
    with open(P_SELF, "w", encoding="utf-8") as f:
        json.dump(sd, f, ensure_ascii=False, indent=2)

# ---------- stdout ----------
print(json.dumps({
    "ok": True,
    "insight": P_INS.as_posix(),
    "learning": P_LEARN.as_posix(),
    "self_describe_touched": bool(applied)
}, ensure_ascii=False, indent=2))
