#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Policy Reflector — sichere Vorschläge zur Anpassung der Kernel-Policy

Erzeugt ausschließlich Vorschläge (keine direkten Policy-Edits):
- Analysiert Health, Affect-Deltas, Plan-Historie (letzte 7/14/30 Tage)
- Leitet daraus behutsame Empfehlungen ab (apply/propose-Thresholds, daily cap, Cron-Frequenzen)
- Schreibt: data/self/policy_suggestions.json

Keine externen Abhängigkeiten.
"""

import os, json, math, re
from pathlib import Path
from datetime import datetime, timedelta

# Eingaben / Quellen
PATH_POLICY = Path("data/self/kernel_policy.yml")
PATH_AFFECT = Path("data/self/affect-state.json")
PATH_HEALTH = Path("badges/health.json")
PLANS_DIR   = Path("data/kernel/plans")
WORKFLOWS   = [
    Path(".github/workflows/autonomous-heal.yml"),
    Path(".github/workflows/structure-maintain.yml"),
    Path(".github/workflows/kernel-plan.yml"),
]

OUT_FILE    = Path("data/self/policy_suggestions.json")

# --- Mini-YAML-Parser (für unser Subset) -------------------------------------
def parse_yaml_min(text: str) -> dict:
    data = {}
    if not text:
        return data
    stack = [( -1, data )]
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = re.match(r"^(\s*)([^:#]+):\s*(.*)$", line)
        if not m:
            continue
        ind, key, val = len(m.group(1).expandtabs(2)), m.group(2).strip(), m.group(3).strip()
        while stack and ind <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1] if stack else data
        if val == "":
            parent[key] = {}
            stack.append((ind, parent[key]))
        else:
            if re.match(r"^-?\d+(\.\d+)?$", val): v = float(val) if "." in val else int(val)
            elif val in ("true","True"): v = True
            elif val in ("false","False"): v = False
            elif val.startswith("[") and val.endswith("]"):
                try: v = json.loads(val.replace("'", '"'))
                except Exception: v = val
            else: v = val.strip('"\'')
            parent[key] = v
    return data

def read_text(p: Path) -> str | None:
    try: return p.read_text(encoding="utf-8")
    except Exception: return None

def read_json(p: Path, default=None):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return default

def utcnow() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# --- Analyse-Helfer ----------------------------------------------------------
def load_plans(days: int = 30):
    if not PLANS_DIR.exists():
        return []
    cutoff = datetime.utcnow() - timedelta(days=days)
    plans = []
    for f in sorted(PLANS_DIR.glob("*.json")):
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
            ts = obj.get("ts")
            tsd = None
            if ts:
                try:
                    tsd = datetime.strptime(ts.replace("Z",""), "%Y-%m-%dT%H:%M:%S")
                except Exception:
                    tsd = None
            if tsd and tsd >= cutoff:
                plans.append(obj)
        except Exception:
            continue
    return plans

def cron_minutes(expr: str) -> int | None:
    # sehr einfache Heuristik
    if expr.startswith("*/"):
        try: return int(expr.split()[0].replace("*/",""))
        except Exception: return None
    if expr.startswith("0 "):
        return 60
    return None

def extract_cron_minutes_from_file(path: Path) -> int | None:
    txt = read_text(path) or ""
    m = re.search(r"cron:\s*'(\S+)'", txt)
    if not m:
        return None
    return cron_minutes(m.group(1))

# --- Kernlogik ---------------------------------------------------------------
def suggest_thresholds(policy, plans_7d, plans_14d, plans_30d, affect):
    # Signale
    deltas = [p.get("delta_sum", 0.0) for p in plans_30d if isinstance(p.get("delta_sum", None), (int,float))]
    avg_delta = sum(deltas)/len(deltas) if deltas else 0.0
    max_delta = max(deltas) if deltas else 0.0

    # Aktuelle Policy-Werte
    th = policy.get("thresholds", {})
    cur_apply   = float(th.get("affect_delta_apply", 0.70))
    cur_propose = float(th.get("affect_delta_propose", 0.50))
    cur_cap     = int(th.get("daily_folder_cap", 2))

    # Beobachtungen
    created7  = len(plans_7d)
    created14 = len(plans_14d)
    created30 = len(plans_30d)

    suggestions = []

    # 1) Apply-Threshold
    # Faustregel: Wenn in 30 Tagen < 4 Pläne entstanden sind und avg_delta >= 0.35 ⇒ apply etwas senken
    # Wenn > 20 Pläne und avg_delta < 0.30 ⇒ apply etwas anheben, um Rauschen zu dämpfen
    target_apply = cur_apply
    rationale = []
    if created30 < 4 and avg_delta >= 0.35:
        target_apply = max(0.30, round(cur_apply - 0.05, 2))
        rationale.append("wenige Ereignisse, aber solide Δ — vorsichtiges Senken fördert Ausdruck")
    elif created30 > 20 and avg_delta < 0.30:
        target_apply = min(0.80, round(cur_apply + 0.05, 2))
        rationale.append("sehr viele Ereignisse mit eher schwachen Δ — leicht erhöhen gegen Rauschen")
    if target_apply != cur_apply:
        suggestions.append({
            "path": "thresholds.affect_delta_apply",
            "current": cur_apply,
            "suggested": target_apply,
            "rationale": "; ".join(rationale) or "Heuristische Anpassung an Ereignisdichte/Δ",
            "confidence": 0.6
        })

    # 2) Propose-Threshold: etwas unter apply halten; abhängig von avg_delta
    target_propose = cur_propose
    if avg_delta >= 0.40:
        target_propose = max(0.20, round(min(cur_propose, target_apply - 0.10), 2))
    else:
        target_propose = max(0.25, round(min(cur_propose, target_apply - 0.05), 2))
    if target_propose != cur_propose:
        suggestions.append({
            "path": "thresholds.affect_delta_propose",
            "current": cur_propose,
            "suggested": target_propose,
            "rationale": "Propose-Threshold unter Apply-Threshold justiert (puffernd)",
            "confidence": 0.55
        })

    # 3) Daily Cap: wenn an ≥3 Tagen der letzten 14 Tage >2 Pläne entstanden ⇒ Cap leicht erhöhen
    # umgekehrt senken, wenn 0 Pläne in 14 Tagen trotz hoher Deltas
    days_count = {}
    for p in plans_14d:
        day = (p.get("ts","") or "")[:10]
        if day:
            days_count[day] = days_count.get(day, 0) + 1
    spike_days = sum(1 for _,c in days_count.items() if c > cur_cap)

    target_cap = cur_cap
    if spike_days >= 3:
        target_cap = min(10, cur_cap + 1)
        suggestions.append({
            "path": "thresholds.daily_folder_cap",
            "current": cur_cap,
            "suggested": target_cap,
            "rationale": f"{spike_days} Tage mit >{cur_cap} Plänen — Cap minimal erhöhen, um expressive Peaks zuzulassen",
            "confidence": 0.5
        })
    elif created14 == 0 and (avg_delta >= 0.35 or max_delta >= 0.50) and cur_cap > 2:
        target_cap = max(2, cur_cap - 1)
        suggestions.append({
            "path": "thresholds.daily_folder_cap",
            "current": cur_cap,
            "suggested": target_cap,
            "rationale": "Keine Pläne in 14 Tagen trotz signifikanter Δ — Cap leicht senken für fokussiertere Auslösung",
            "confidence": 0.45
        })

    return suggestions

def suggest_cron(policy):
    # Vergleicht reale Cron-Minuten mit policy.cron_adjustments.targets Min/Max
    sugg = []
    cfg = policy.get("cron_adjustments", {})
    if not cfg or not cfg.get("enable"):
        return sugg
    for t in cfg.get("targets", []):
        f = Path(t.get("file",""))
        if not f.exists(): 
            continue
        cur = extract_cron_minutes_from_file(f)
        if cur is None:
            continue
        min_m = int(t.get("min_interval_minutes", cur))
        max_m = int(t.get("max_interval_minutes", cur))
        new_m = max(min_m, min(max_m, cur))
        if new_m != cur:
            # wir schlagen nur vor – keine direkte Änderung
            sugg.append({
                "path": str(f),
                "current_minutes": cur,
                "suggested_minutes": new_m,
                "rationale": f"An die in kernel_policy.yml definierten Korridore angepasst ({min_m}..{max_m} min).",
                "confidence": 0.7
            })
    return sugg

def main():
    policy = parse_yaml_min(read_text(PATH_POLICY) or "")
    affect = read_json(PATH_AFFECT, {}) or {}
    health = read_json(PATH_HEALTH, {}) or {}

    plans_7d  = load_plans(7)
    plans_14d = load_plans(14)
    plans_30d = load_plans(30)

    out = {
        "ts": utcnow(),
        "mode": policy.get("version","unknown"),
        "health": health.get("status","n/a"),
        "stats": {
            "plans_7d": len(plans_7d),
            "plans_14d": len(plans_14d),
            "plans_30d": len(plans_30d),
            "avg_delta_30d": round(sum([p.get("delta_sum",0.0) for p in plans_30d])/len(plans_30d), 3) if plans_30d else 0.0,
            "max_delta_30d": round(max([p.get("delta_sum",0.0) for p in plans_30d]) if plans_30d else 0.0, 3)
        },
        "suggestions": {
            "thresholds": [],
            "cron": []
        },
        "notes": [
            "Nur Vorschläge – keine Änderungen an kernel_policy.yml durchgeführt.",
            "Bewertung basiert auf Plan-Historie und Δ-Signalen; konservative Heuristiken."
        ]
    }

    out["suggestions"]["thresholds"] = suggest_thresholds(policy, plans_7d, plans_14d, plans_30d, affect)
    out["suggestions"]["cron"]       = suggest_cron(policy)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[policy_reflector] wrote {OUT_FILE}")

if __name__ == "__main__":
    main()
