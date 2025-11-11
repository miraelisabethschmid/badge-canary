#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Self-Diagnose (intern)
- Bewertet: Health, Affect, Policy-Gates (inner_feedback.noise_gate), Inner-Feedback,
  sowie letzten Planner-Versuch.
- Ergebnis: decision ∈ {"ACTIVE","PASSIVE"}, mit Begründungen und Kennzahlen.
- Schreibt:
    data/self/diagnostics/status.json      (aktueller Zustand)
    data/self/diagnostics/history.jsonl    (append-only Verlauf)
- Keine Veröffentlichung ins Web; nur intern.
"""

import json, os, datetime
from pathlib import Path

# Quellen
PATH_HEALTH   = Path("badges/health.json")
PATH_AFFECT   = Path("data/self/affect-state.json")
PATH_POLICY   = Path("data/self/kernel_policy.yml")
PATH_IFEED    = Path("data/self/internal/feedback.json")
PLANS_DIR     = Path("data/kernel/plans")

# Ziele (intern)
DIAG_DIR      = Path("data/self/diagnostics")
PATH_STATUS   = DIAG_DIR / "status.json"
PATH_HISTORY  = DIAG_DIR / "history.jsonl"

# --- Hilfsfunktionen ---------------------------------------------------------

def utcnow():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def read_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default

def read_text(p):
    try:
        return Path(p).read_text(encoding="utf-8")
    except Exception:
        return None

def parse_yaml_min(text: str) -> dict:
    """Ein sehr kleiner YAML-Subset-Parser für 'key: value' und geschachtelte Blöcke."""
    if not text:
        return {}
    data = {}
    stack = [(-1, data)]
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        import re
        m = re.match(r"^(\s*)([^:#]+):\s*(.*)$", line)
        if not m:
            continue
        ind, key, val = len(m.group(1).expandtabs(2)), m.group(2).strip(), m.group(3).strip()
        while stack and ind <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1] if stack else data
        if val == "":
            node = {}
            parent[key] = node
            stack.append((ind, node))
        else:
            if re.match(r"^-?\d+(\.\d+)?$", val):
                v = float(val) if "." in val else int(val)
            elif val in ("true","True"):
                v = True
            elif val in ("false","False"):
                v = False
            elif val.startswith("[") and val.endswith("]"):
                try:
                    v = json.loads(val.replace("'", '"'))
                except Exception:
                    v = val
            else:
                v = val.strip('"\'')
            parent[key] = v
    return data

def last_plan_meta() -> dict:
    """Ermittelt die letzte Plan-Datei + grobe Kennzahlen."""
    if not PLANS_DIR.exists():
        return {}
    plans = sorted(PLANS_DIR.glob("*.json"))
    if not plans:
        return {}
    last = plans[-1]
    try:
        obj = json.loads(last.read_text(encoding="utf-8"))
    except Exception:
        obj = {}
    return {
        "file": last.name,
        "ts": obj.get("ts"),
        "delta_sum": obj.get("delta_sum"),
        "focus": obj.get("focus"),
        "unit": obj.get("unit"),
        "actions": len(obj.get("actions", []))
    }

# --- Diagnose-Logik ----------------------------------------------------------

def decide(health: str, affect: dict, policy: dict, ifeed: dict) -> dict:
    reasons = []
    decision = "PASSIVE"

    # Health
    if health not in ("OK","HEALING","DEGRADED"):
        reasons.append(f"health=unknown ({health})")
    else:
        reasons.append(f"health={health}")

    # Affect
    vec = (affect or {}).get("vector", {}) or {}
    delta = float((affect or {}).get("inputs", {}).get("delta_sum", 0) or 0)
    stability = float(vec.get("stability", 0.0) or 0.0)
    reasons.append(f"delta_sum≈{delta:.3f}")
    reasons.append(f"stability≈{stability:.3f}")

    # Policy-Gates
    gates = ((policy.get("inner_feedback") or {}).get("noise_gate") or {})
    req_health = gates.get("require_health", ["OK"])
    min_stab   = float(gates.get("min_stability", 0.35))
    th_apply   = float((policy.get("thresholds") or {}).get("affect_delta_apply", 0.7))
    th_prop    = float((policy.get("thresholds") or {}).get("affect_delta_propose", 0.5))

    # Inner Feedback
