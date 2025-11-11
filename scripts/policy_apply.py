#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Policy Auto-Apply
Übernimmt Vorschläge aus data/self/policy_suggestions.json automatisch in
data/self/kernel_policy.yml – ohne Rückfragen.

Sicherheitsmerkmale:
- Guard-Variablen: POLICY_AUTO=1 und KERNEL_AUTONOMY=1 nötig
- Erlaubte Pfade/Typen whitelisten (nur numerische Thresholds + Daily Cap)
- Werte-Bounds (numerisch & sinnvoll)
- Backup vorher: data/self/kernel_policy.backup.yml
- Audit-Log: data/self/policy_changes.jsonl
- Idempotent: überspringt, wenn kein effektiver Unterschied

Es werden aktuell NUR folgende Felder automatisiert angepasst:
- thresholds.affect_delta_apply       (float, 0.10..0.90)
- thresholds.affect_delta_propose     (float, 0.05..0.85)
- thresholds.daily_folder_cap         (int,   1..20)

Cron-Vorschläge werden NICHT automatisch angewendet (bewusste Sicherung).
"""

import os, re, json, shutil
from pathlib import Path
from datetime import datetime

PATH_POLICY = Path("data/self/kernel_policy.yml")
PATH_SUGG   = Path("data/self/policy_suggestions.json")
PATH_BACKUP = Path("data/self/kernel_policy.backup.yml")
PATH_AUDIT  = Path("data/self/policy_changes.jsonl")

RE_FLOAT = r"([0-9]+(?:\.[0-9]+)?)"
RE_INT   = r"([0-9]+)"

# Regex-Ziele (einfaches YAML, key: wert)
PATTERNS = {
    "thresholds.affect_delta_apply":    re.compile(r"(^\s*affect_delta_apply:\s*)" + RE_FLOAT + r"\s*$", re.MULTILINE),
    "thresholds.affect_delta_propose":  re.compile(r"(^\s*affect_delta_propose:\s*)" + RE_FLOAT + r"\s*$", re.MULTILINE),
    "thresholds.daily_folder_cap":      re.compile(r"(^\s*daily_folder_cap:\s*)"   + RE_INT   + r"\s*$", re.MULTILINE),
}

# Bounds
BOUNDS = {
    "thresholds.affect_delta_apply":   (0.10, 0.90),
    "thresholds.affect_delta_propose": (0.05, 0.85),
    "thresholds.daily_folder_cap":     (1, 20),
}

ALLOWED_PATHS = set(PATTERNS.keys())

def now():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def load_json(p, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def apply_numeric(text, key, new_val):
    pat = PATTERNS[key]
    m = pat.search(text)
    if not m:
        return text, False
    prefix = m.group(1)
    old = m.group(2)
    if str(old) == str(new_val):
        return text, False
    return pat.sub(prefix + str(new_val), text, count=1), True

def main():
    # Guards
    if os.getenv("POLICY_AUTO", "") != "1" or os.getenv("KERNEL_AUTONOMY", "") != "1":
        print("[policy_apply] guard off (POLICY_AUTO and/or KERNEL_AUTONOMY not '1') – exiting.")
        return

    sugg = load_json(PATH_SUGG, {}) or {}
    suggestions = sugg.get("suggestions", {})
    th_suggs = suggestions.get("thresholds", [])
    if not th_suggs:
        print("[policy_apply] no threshold suggestions – nothing to do.")
        return

    original = PATH_POLICY.read_text(encoding="utf-8")
    updated  = original
    changes  = []

    # Sammle letzte bekannte aktuelle Werte (für Audit)
    current_vals = {}
    for k, pat in PATTERNS.items():
        m = pat.search(original)
        if m:
            current_vals[k] = m.group(2)

    for s in th_suggs:
        path = s.get("path")
        if path not in ALLOWED_PATHS:
            continue
        suggested = s.get("suggested", None)
        if suggested is None:
            continue

        lo, hi = BOUNDS[path]
        if "cap" in path:
            # Integer
            try:
                val = int(round(float(suggested)))
            except Exception:
                continue
            val = int(clamp(val, lo, hi))
        else:
            # Float
            try:
                val = float(suggested)
            except Exception:
                continue
            val = float(f"{clamp(val, lo, hi):.2f}")

        updated2, did = apply_numeric(updated, path, val)
        if did:
            before = current_vals.get(path, None)
            changes.append({
                "path": path, "from": before, "to": val,
                "rationale": s.get("rationale", ""),
                "confidence": s.get("confidence", None)
            })
            updated = updated2

    if not changes:
        print("[policy_apply] no effective changes – exiting.")
        return

    # Backup
    try:
        shutil.copyfile(PATH_POLICY, PATH_BACKUP)
        print(f"[policy_apply] backup written: {PATH_BACKUP}")
    except Exception as e:
        print("[policy_apply] backup failed:", e)

    # Version-String optional erhöhen (…-expressive → …-expressive+auto)
    ver_pat = re.compile(r'(^\s*version:\s*)"([^"]+)"\s*$', re.MULTILINE)
    m = ver_pat.search(updated)
    if m:
        v_old = m.group(2)
        v_new = v_old if v_old.endswith("+auto") else v_old + "+auto"
        updated = ver_pat.sub(r'\1"'+v_new+r'"', updated, count=1)

    # Schreiben
    PATH_POLICY.write_text(updated, encoding="utf-8")

    # Audit
    PATH_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with PATH_AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": now(),
            "applied": changes
        }, ensure_ascii=False) + "\n")

    print("[policy_apply] applied changes:", json.dumps(changes, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
