  #!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Self-Diagnostics — internes Entscheidungsfenster (einzelne JSON-Datei)

Liest: 
- data/self/kernel_policy.yml
- badges/health.json
- data/self/affect-state.json
- data/self/internal/feedback.json (optional)
- data/goals/current.json (optional)

Schreibt (idempotent, rein intern):
- data/self/internal/diagnostics.json

Zweck:
- Zeigt, ob Mira heute/jetzt HANDLEN würde und WARUM (Gates, Schwellen, Delten, Hinweise).
- Keine externen Abhängigkeiten, reiner Python-Stdlib.
"""

from __future__ import annotations
import json, os, re, datetime
from pathlib import Path

# ---- Pfade -------------------------------------------------------------------

P_POLICY   = Path("data/self/kernel_policy.yml")
P_HEALTH   = Path("badges/health.json")
P_AFFECT   = Path("data/self/affect-state.json")
P_IFEED    = Path("data/self/internal/feedback.json")     # optional
P_GOALS    = Path("data/goals/current.json")              # optional
P_OUT      = Path("data/self/internal/diagnostics.json")

# ---- Utils -------------------------------------------------------------------

def utcnow() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def read_text(p: Path) -> str|None:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return None

# Minimales YAML-Subset für unsere Policy (Key: Value + einfache Objekte)
def parse_yaml_min(text: str) -> dict:
    if not text:
        return {}
    data, stack = {}, [(-1, {})]
    root = stack[-1][1]
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^(\s*)([^:#]+):\s*(.*)$", line)
        if not m:
            continue
        ind = len(m.group(1).expandtabs(2))
        key = m.group(2).strip()
        val = m.group(3).strip()
        while stack and ind <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1] if stack else root
        if val == "":
            parent[key] = {}
            stack.append((ind, parent[key]))
        else:
            if re.match(r"^-?\d+(\.\d+)?$", val):
                v = float(val) if "." in val else int(val)
            elif val in ("true","True"): v = True
            elif val in ("false","False"): v = False
            elif val.startswith("[") and val.endswith("]"):
                try: v = json.loads(val.replace("'", '"'))
                except Exception: v = val
            else: v = val.strip("\"'")
            parent[key] = v
    data = root
    return data

# ---- Kernlogik ---------------------------------------------------------------

def compute_effective_delta(aff: dict, ifeed: dict|None, policy: dict, health_status: str) -> dict:
    """
    Wendet (falls erlaubt) das Noise-Gate der Policy auf das innere Feedback an
    und liefert die effektive Δ sowie Begründungen zurück.
    """
    reasons = []
    vec = (aff.get("vector") or {})
    base_delta = float(aff.get("inputs", {}).get("delta_sum", 0) or 0.0)
    focus_in  = aff.get("inputs", {}).get("focus") or None

    eff_delta = base_delta
    eff_focus = focus_in
    took_hint = False
    bonus_applied = 0.0
    gates_ok = True

    gate_cfg = (policy.get("inner_feedback") or {}).get("noise_gate", {})
    enable_if = (policy.get("inner_feedback") or {}).get("enable", False)

    if not enable_if or not ifeed:
        reasons.append("inner_feedback disabled or missing")
        return {
            "effective_delta": round(eff_delta, 3),
            "effective_focus": eff_focus,
            "took_focus_hint": took_hint,
            "bonus_applied": round(bonus_applied, 3),
            "gates_ok": False if not enable_if else True,
            "reasons": reasons
        }

    require_health = gate_cfg.get("require_health", ["OK"])
    min_stab = float(gate_cfg.get("min_stability", 0.35))
    min_conf = float(gate_cfg.get("min_confidence", 0.60))
    max_abs  = float(gate_cfg.get("max_abs_bonus", 0.08))

    stability = float(vec.get("stability", 0.5) or 0.5)
    if health_status not in require_health:
        reasons.append(f"health '{health_status}' not in {require_health}")
        gates_ok = False
    if stability < min_stab:
        reasons.append(f"stability {stability:.2f} < {min_stab:.2f}")
        gates_ok = False

    if not gates_ok:
        return {
            "effective_delta": round(eff_delta, 3),
            "effective_focus": eff_focus,
            "took_focus_hint": took_hint,
            "bonus_applied": round(bonus_applied, 3),
            "gates_ok": False,
            "reasons": reasons
        }

    # Gate offen → vorsichtige Anwendung
    bonus = float(ifeed.get("delta_bonus", 0.0) or 0.0)
    conf  = float(ifeed.get("confidence", 0.0) or 0.0)
    hint  = ifeed.get("focus_hint")

    if bonus > 0: bonus = min(bonus, max_abs)
    if bonus < 0: bonus = max(bonus, -max_abs)
    eff_delta = max(0.0, round(base_delta + bonus, 3))
    bonus_applied = bonus

    if hint and conf >= min_conf:
        eff_focus = hint
        took_hint = True
    else:
        if hint and conf < min_conf:
            reasons.append(f"focus_hint confidence {conf:.2f} < {min_conf:.2f}")

    return {
        "effective_delta": round(eff_delta, 3),
        "effective_focus": eff_focus,
        "took_focus_hint": took_hint,
        "bonus_applied": round(bonus_applied, 3),
        "gates_ok": True,
        "reasons": reasons
    }

def main():
    policy = parse_yaml_min(read_text(P_POLICY) or "")
    health = read_json(P_HEALTH, {}) or {}
    aff    = read_json(P_AFFECT, {}) or {}
    ifeed  = read_json(P_IFEED, None)
    goals  = read_json(P_GOALS, {}) or {}

    health_status = str(health.get("status", "unknown"))
    thresholds = policy.get("thresholds", {}) or {}
    thr_apply   = float(thresholds.get("affect_delta_apply", 0.7))
    thr_propose = float(thresholds.get("affect_delta_propose", 0.5))
    cap_daily   = int(thresholds.get("daily_folder_cap", 2))

    # Basiswerte
    vec = aff.get("vector", {}) or {}
    base = {
        "delta_sum": float(aff.get("inputs", {}).get("delta_sum", 0) or 0.0),
        "focus_in":  aff.get("inputs", {}).get("focus") or goals.get("focus") or "insight",
        "valence":   float(vec.get("valence", 0.5) or 0.5),
        "arousal":   float(vec.get("arousal", 0.3) or 0.3),
        "stability": float(vec.get("stability", 0.5) or 0.5),
    }

    # Effektive Δ/Fokus nach Gate
    eff = compute_effective_delta(aff, ifeed, policy, health_status)

    # Ableitung des Entscheidungsstatus
    may_propose = (eff["effective_delta"] >= thr_propose)
    may_apply   = (eff["effective_delta"] >= thr_apply) and (os.getenv(policy.get("apply_guard",{}).get("env_var","KERNEL_AUTONOMY"),"") == policy.get("apply_guard",{}).get("required_value","1"))

    decision = (
        "APPLY" if may_apply else
        "PROPOSE" if may_propose else
        "IDLE"
    )

    out = {
        "ts_utc": utcnow(),
        "status": {
            "health": health_status,
            "decision": decision
        },
        "inputs": {
            "base": base,
            "goals_focus": goals.get("focus"),
            "inner_feedback_present": bool(ifeed is not None)
        },
        "policy": {
            "version": policy.get("version"),
            "thresholds": {
                "affect_delta_apply": thr_apply,
                "affect_delta_propose": thr_propose,
                "daily_folder_cap": cap_daily
            },
            "apply_guard": policy.get("apply_guard", {}),
            "inner_feedback_gate": (policy.get("inner_feedback") or {}).get("noise_gate", {})
        },
        "effective": {
            "delta": eff["effective_delta"],
            "focus": eff["effective_focus"],
            "bonus_applied": eff["bonus_applied"],
            "gates_ok": eff["gates_ok"],
            "took_focus_hint": eff["took_focus_hint"],
            "reasons": eff["reasons"]
        },
        "env": {
            "KERNEL_AUTONOMY": os.getenv("KERNEL_AUTONOMY", None),
            "POLICY_AUTO": os.getenv("POLICY_AUTO", None)
        }
    }

    # Schreiben (idempotent)
    P_OUT.parent.mkdir(parents=True, exist_ok=True)
    P_OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[self-diagnostics] wrote {P_OUT}")

if __name__ == "__main__":
    main()
