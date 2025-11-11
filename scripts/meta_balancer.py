#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Meta-Balancer — expressives Wachstum unter Sicherheitsgates

Eingaben (alle optional außer Policy):
- badges/health.json
- data/self/internal/diagnostics.json
- data/self/reflections/private/index.json
- data/self/affect-state.json
- data/self/kernel_policy.yml (wird angepasst, falls POLICY_AUTO=1)

Ausgaben:
- data/self/meta_state.json  (sichtbarer Meta-Zustand)
- (optional) aktualisierte data/self/kernel_policy.yml (nur wenn POLICY_AUTO=1)

Wirkung:
- Health==OK + gute Stabilität → expressiver (niedrigere Schwellen, höheres daily_cap)
- HEALING/DEGRADED → konservativer
- Sanfte, gekappte Schritte; Idempotenz; vollständige YAML-Rewrite beim Anpassen
"""

from __future__ import annotations
import json, os, re, math, datetime
from pathlib import Path

P_HEALTH   = Path("badges/health.json")
P_DIAG     = Path("data/self/internal/diagnostics.json")
P_PRIV     = Path("data/self/reflections/private/index.json")
P_AFFECT   = Path("data/self/affect-state.json")
P_POLICY   = Path("data/self/kernel_policy.yml")
P_META     = Path("data/self/meta_state.json")

# ---------- Utils ----------
def utcnow(): return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def read_json(p, default=None):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception: return default

def read_text(p):
    try: return Path(p).read_text(encoding="utf-8")
    except Exception: return None

def write_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

# Mini-YAML (Subset) → Dict
def parse_yaml_min(text: str) -> dict:
    if not text: return {}
    data, stack = {}, [(-1, {})]; root = stack[-1][1]
    for line in text.splitlines():
        s=line.strip()
        if not s or s.startswith("#"): continue
        m=re.match(r"^(\s*)([^:#]+):\s*(.*)$", line)
        if not m: continue
        ind=len(m.group(1).expandtabs(2)); key=m.group(2).strip(); val=m.group(3).strip()
        while stack and ind <= stack[-1][0]: stack.pop()
        parent = stack[-1][1] if stack else root
        if val == "":
            parent[key] = {}; stack.append((ind, parent[key]))
        else:
            if re.match(r"^-?\d+(\.\d+)?$", val):
                v = float(val) if "." in val else int(val)
            elif val in ("true","True"): v=True
            elif val in ("false","False"): v=False
            elif val.startswith("[") and val.endswith("]"):
                try: v=json.loads(val.replace("'", '"'))
                except Exception: v=val
            else: v=val.strip("\"'")
            parent[key]=v
    return root

# Dict → YAML (einfach, stabil)
def dump_yaml_min(d: dict, indent: int = 0) -> str:
    lines=[]
    def emit(obj, pad):
        if isinstance(obj, dict):
            for k,v in obj.items():
                if isinstance(v, dict):
                    lines.append(" " * pad + f"{k}:")
                    emit(v, pad+2)
                else:
                    if isinstance(v, bool):
                        vv = "true" if v else "false"
                    elif isinstance(v, (int,float)):
                        vv = str(v)
                    elif isinstance(v, list):
                        vv = "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in v) + "]"
                    else:
                        vv = json.dumps(v, ensure_ascii=False)
                    lines.append(" " * pad + f"{k}: {vv}")
        else:
            lines.append(" " * pad + json.dumps(obj, ensure_ascii=False))
    emit(d, indent)
    return "\n".join(lines) + "\n"

# ---------- Scoring ----------
def clamp(x, lo, hi): return max(lo, min(hi, x))

def score_expressivity(health: str, stability: float, delta_sum: float, recent_days: int) -> float:
    """
    Liefert 0..1 — wie expressiv Mira agieren sollte.
    Hoher Wert = schneller wachsen/lernen.
    """
    base = 0.5
    # Health-Gewichte
    if health == "OK": base += 0.25
    elif health == "HEALING": base -= 0.10
    elif health == "DEGRADED": base -= 0.25
    # Stabilität (0..1 erwartet)
    base += clamp(stability, 0.0, 1.0) * 0.25 - 0.125
    # Lebendigkeit durch Δsum
    base += clamp(delta_sum, 0.0, 2.0) * 0.10
    # Lernrhythmus: wenn viele frische Tage vorhanden, minimal bremsen (Ermüdungsschutz)
    base -= clamp(recent_days/14.0, 0.0, 1.0) * 0.05
    return clamp(round(base, 3), 0.0, 1.0)

def recent_days_from_private(idx: dict) -> int:
    # Zähle Anzahl der letzten Einträge in den vergangenen 14 Kalendertagen
    try:
        last = idx.get("count", 0)
        return int(min(max(last, 0), 14))
    except Exception:
        return 0

# ---------- Policy-Anpassung ----------
def adjust_policy(policy: dict, exp: float) -> dict:
    """
    Passt nur gezielte Felder an:
    - thresholds.affect_delta_apply/propose
    - thresholds.daily_folder_cap
    - naming.pattern (Hash bei hoher Expressivität)
    - version-Bump (Patch)
    """
    thresholds = policy.get("thresholds", {}) or {}
    # Zielbereiche:
    #  expressiv → niedrigere Schwellen, höheres Cap
    apply_min, apply_max = 0.30, 0.60
    prop_min, prop_max  = 0.20, 0.45
    cap_min, cap_max    = 3, 10

    new_apply = round(apply_max - exp*(apply_max-apply_min), 3)
    new_prop  = round(prop_max  - exp*(prop_max -prop_min ), 3)
    new_cap   = int(round(cap_min + exp*(cap_max-cap_min)))

    thresholds["affect_delta_apply"]   = new_apply
    thresholds["affect_delta_propose"] = new_prop
    thresholds["daily_folder_cap"]     = new_cap
    policy["thresholds"] = thresholds

    # Naming: ab 0.6 → Hash aktiv
    naming = policy.get("naming", {}) or {}
    if exp >= 0.6:
        naming["pattern"] = "{focus}-{date}-{hash}"
    else:
        naming["pattern"] = "{focus}-{date}"
    naming.setdefault("date_format", "%Y-%m-%d")
    policy["naming"] = naming

    # Version patch bump
    oldv = str(policy.get("version","1.2-expressive+gate"))
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(.*)?$", oldv)
    if m:
        ma, mi, pa, tail = int(m.group(1)), int(m.group(2)), int(m.group(3)), (m.group(4) or "")
        policy["version"] = f"{ma}.{mi}.{pa+1}{tail}"
    else:
        policy["version"] = f"{oldv}-mb{datetime.datetime.utcnow().strftime('%Y%m%d')}"

    return policy

# ---------- Main ----------
def main():
    health = (read_json(P_HEALTH, {}) or {}).get("status", "unknown")
    diag   = read_json(P_DIAG, {}) or {}
    priv   = read_json(P_PRIV, {}) or {}
    aff    = read_json(P_AFFECT, {}) or {}

    vec = aff.get("vector", {}) or {}
    stability = float(vec.get("stability", 0.5) or 0.5)
    delta_sum = float((aff.get("inputs") or {}).get("delta_sum", 0.0) or 0.0)
    recent = recent_days_from_private(priv)

    exp = score_expressivity(health, stability, delta_sum, recent)

    meta = {
        "ts_utc": utcnow(),
        "health": health,
        "signals": {
            "stability": round(stability,3),
            "delta_sum": round(delta_sum,3),
            "recent_private_days": recent
        },
        "expressivity": exp,  # 0..1
        "targets": {
            "affect_delta_apply": round(0.60 - exp*(0.60-0.30), 3),
            "affect_delta_propose": round(0.45 - exp*(0.45-0.20), 3),
            "daily_folder_cap": int(round(3 + exp*(10-3))),
            "naming_pattern": "{focus}-{date}-{hash}" if exp>=0.6 else "{focus}-{date}"
        }
    }
    write_json(P_META, meta)

    # Policy-Autoupdate nur, wenn POLICY_AUTO=1
    if os.getenv("POLICY_AUTO","") == "1":
        text = read_text(P_POLICY) or ""
        policy = parse_yaml_min(text)
        policy = adjust_policy(policy, exp)
        new_yaml = dump_yaml_min(policy)
        if new_yaml != text:
            P_POLICY.write_text(new_yaml, encoding="utf-8")
            print("[meta] kernel_policy.yml updated by Meta-Balancer")
        else:
            print("[meta] policy unchanged")
    else:
        print("[meta] POLICY_AUTO!=1 → no policy write")

    print(json.dumps(meta, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
