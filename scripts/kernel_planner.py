#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Kernel Planner — structural freedom within guards

Funktionen:
1) Aus policies (data/self/kernel_policy.yml) Regeln laden.
2) Aus Zuständen (affect-state, goals, health) Handlungsbedarf ableiten.
3) Plan-Dateien unter data/kernel/plans/<ts>.json erzeugen (propose).
4) Nur wenn Guard aktiv (env KERNEL_AUTONOMY=1) und Δsum ≥ apply-Threshold:
   → Pläne anwenden (Ordner + Artefakte), streng idempotent.
5) (Optional) Cron-Frequenzen in erlaubten Workflows leicht anpassen.

Keine externen Abhängigkeiten. Keine Frage-Persistenz. Sicher & nachvollziehbar.
"""

import os, re, json, datetime, hashlib, glob
from pathlib import Path

# Pfade
PATH_POLICY = Path("data/self/kernel_policy.yml")
PATH_AFFECT = Path("data/self/affect-state.json")
PATH_GOALS  = Path("data/goals/current.json")
PATH_HEALTH = Path("badges/health.json")
PLANS_DIR   = Path("data/kernel/plans")

def utcnow():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def today_str(fmt="%Y-%m-%d"):
    return datetime.datetime.utcnow().strftime(fmt)

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

def write_json(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

# Minimal-Parser für unser YAML-Subset (key: value & einfache Maps)
def parse_yaml_min(text):
    data = {}
    if not text:
        return data
    indent_stack = [(-1, data)]
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = re.match(r'^(\s*)([^:#]+):\s*(.*)$', line)
        if not m:
            continue
        ind, key, val = len(m.group(1).expandtabs(2)), m.group(2).strip(), m.group(3).strip()
        while indent_stack and ind <= indent_stack[-1][0]:
            indent_stack.pop()
        parent = indent_stack[-1][1] if indent_stack else data
        if val == "":
            parent[key] = {}
            indent_stack.append((ind, parent[key]))
        else:
            # primitive interpretation
            if re.match(r"^-?\d+(\.\d+)?$", val): v = float(val) if "." in val else int(val)
            elif val in ("true","True"): v = True
            elif val in ("false","False"): v = False
            elif val.startswith("[") and val.endswith("]"):
                try: v = json.loads(val.replace("'", '"'))
                except Exception: v = val
            else: v = val.strip('"\'')
            parent[key] = v
    return data

def load_policy():
    txt = read_text(PATH_POLICY)
    return parse_yaml_min(txt or "")

def affect_delta():
    aff = read_json(PATH_AFFECT, {}) or {}
    try:
        return float(aff.get("inputs", {}).get("delta_sum", 0) or 0)
    except Exception:
        return 0.0

def current_focus():
    aff = read_json(PATH_AFFECT, {}) or {}
    goals = read_json(PATH_GOALS, {}) or {}
    return (aff.get("inputs", {}).get("focus")
            or goals.get("focus")
            or "insight")

def count_today_created(root="data", date_str=None):
    date_str = date_str or today_str()
    n = 0
    for p in Path(root).rglob("*"):
        try:
            if p.is_dir() and date_str in p.name:
                n += 1
        except Exception:
            pass
    return n

def safe_match_allowed(path_str, allowed_patterns):
    from fnmatch import fnmatch
    return any(fnmatch(path_str, pat) for pat in allowed_patterns)

def apply_plan(plan, policy):
    """Wendet einen Plan an, wenn erlaubt. Idempotent."""
    created = []
    for item in plan.get("actions", []):
        kind = item.get("kind")
        target = Path(item.get("path", ""))
        if not target:
            continue
        # Schreib-Whitelist prüfen
        if not safe_match_allowed(str(target), policy.get("allowed_artifacts", [])):
            print(f"[kernel] skip (not allowed): {target}")
            continue

        if kind == "mkdir":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.mkdir(parents=True, exist_ok=True)
            created.append(str(target))
        elif kind == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            # Idempotenz: nur schreiben, wenn Inhalt sich ändert
            new_content = item.get("content", "")
            if target.exists():
                old = target.read_text(encoding="utf-8")
                if old == new_content:
                    continue
            target.write_text(new_content, encoding="utf-8")
            created.append(str(target))
        elif kind == "index_append":
            idx = {}
            if target.exists():
                try: idx = json.loads(target.read_text(encoding="utf-8"))
                except Exception: idx = {}
            files = set(idx.get("files", []))
            for rel in item.get("entries", []):
                files.add(rel)
            idx["files"] = sorted(files)
            target.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")
            created.append(str(target))
    return created

def adjust_cron(policy):
    cfg = policy.get("cron_adjustments", {})
    if not cfg or not cfg.get("enable"):
        return []
    changed = []
    for tgt in cfg.get("targets", []):
        f = Path(tgt.get("file",""))
        if not f.exists(): 
            continue
        y = f.read_text(encoding="utf-8")
        # cron: '*/60 * * * *' → wir versuchen Minutenwert zu erfassen
        m = re.search(r"cron:\s*'(\S+)'", y)
        if not m: 
            continue
        expr = m.group(1)
        # nur simple "*/N" oder "0 * * * *" Formen anfassen
        minutes = None
        if expr.startswith("*/"):
            try: minutes = int(expr.split()[0].replace("*/",""))
            except Exception: minutes = None
        elif expr.startswith("0 "):
            minutes = 60
        if minutes is None: 
            continue
        min_min = int(tgt.get("min_interval_minutes", minutes))
        max_min = int(tgt.get("max_interval_minutes", minutes))
        new_minutes = max(min_min, min(max_min, minutes))
        if new_minutes != minutes:
            new_expr = f"*/{new_minutes} * * * *" if new_minutes != 60 else "0 * * * *"
            y2 = re.sub(r"(cron:\s*')(\S+)(')", rf"\1{new_expr}\3", y, count=1)
            if y2 != y:
                f.write_text(y2, encoding="utf-8")
                changed.append(str(f))
    return changed

def make_note_content(title, body):
    return f"# {title}\n\n{body}\n\n— {utcnow()}"

def make_manifest_content(meta: dict):
    return json.dumps(meta, indent=2, ensure_ascii=False)

def plan_from_state(policy):
    delta = affect_delta()
    focus = current_focus()
    date_fmt = policy.get("naming", {}).get("date_format", "%Y-%m-%d")
    name_pat = policy.get("naming", {}).get("pattern", "{focus}-{date}")
    date_str = today_str(date_fmt)
    slug = (focus or "insight").lower()
    unit_name = name_pat.format(focus=slug, date=date_str)

    # daily cap
    if count_today_created(root="data", date_str=date_str) >= int(policy.get("thresholds",{}).get("daily_folder_cap", 2)):
        return None

    ft = policy.get("focus_targets", {}).get(slug) or policy.get("focus_targets", {}).get(focus) \
         or {"root":"data/thoughts","kind":"note","template":"note.md"}
    root = Path(ft.get("root","data/thoughts"))
    kind = ft.get("kind","note")

    target_dir = root / unit_name
    actions = []

    if delta >= float(policy.get("thresholds",{}).get("affect_delta_propose", 0.5)):
        # Basisartefakte planen
        if kind in ("note","reflection"):
            note_path = target_dir / "note.md"
            content = make_note_content(
                title=f"{slug} — {date_str}",
                body=f"Autonome Notiz aufgrund Δsum≈{delta:.3f} (focus={focus})."
            )
            actions += [
                {"kind":"mkdir","path":str(target_dir)},
                {"kind":"write","path":str(note_path), "content":content}
            ]
        elif kind in ("prototype","vision"):
            manifest = {
                "kind": kind,
                "created": utcnow(),
                "reason": "affect_delta",
                "delta_sum": round(delta,3),
                "focus": focus
            }
            actions += [
                {"kind":"mkdir","path":str(target_dir)},
                {"kind":"write","path":str(target_dir / "manifest.json"), "content": make_manifest_content(manifest)},
                {"kind":"write","path":str(target_dir / "seed.txt"), "content": f"seed: {kind}\nfocus: {focus}\ndelta: {round(delta,3)}\ncreated: {utcnow()}\n"}
            ]

        # Prototyp-Root index ergänzen (falls vorhanden)
        if str(root).startswith("data/prototypes"):
            root_index = Path("data/prototypes/index.json")
            entries = []
            try:
                rel = str(target_dir.relative_to(Path("data/prototypes")))
                entries = [rel]
            except Exception:
                pass
            actions.append({"kind":"index_append","path":str(root_index), "entries": entries})

    if not actions:
        return None

    plan = {
        "ts": utcnow(),
        "delta_sum": round(delta,3),
        "apply_guard": {
            "env": policy.get("apply_guard",{}).get("env_var","KERNEL_AUTONOMY"),
            "required_value": policy.get("apply_guard",{}).get("required_value","1")
        },
        "focus": focus,
        "unit": unit_name,
        "actions": actions
    }
    return plan

def main():
    policy = load_policy()
    delta = affect_delta()

    plan = plan_from_state(policy)
    if not plan:
        print("[kernel] no plan generated (threshold/cap not met)")
        return

    # Plan persistieren (audit)
    plan_path = PLANS_DIR / (plan["ts"].replace(":","").replace("-","").replace("T","_").replace("Z","") + ".json")
    write_json(plan_path, plan)
    print(f"[kernel] plan proposed: {plan_path}")

    # Guard prüfen
    guard_env = plan["apply_guard"]["env"]
    guard_needed = plan["apply_guard"]["required_value"]
    guard_val = os.getenv(guard_env, "")
    may_apply = (guard_val == guard_needed) and (delta >= float(load_policy().get("thresholds",{}).get("affect_delta_apply",0.7)))

    created = []
    cron_changed = []

    if may_apply:
        created = apply_plan(plan, policy)
        # Cron-Anpassung (optional & streng limitiert)
        if policy.get("cron_adjustments",{}).get("enable"):
            cron_changed = adjust_cron(policy)
        print(f"[kernel] plan applied: {len(created)} artifacts, cron_changed={len(cron_changed)}")
    else:
        print(f"[kernel] guard prevents apply (env {guard_env}='{guard_val}' needed '{guard_needed}') or delta below apply-threshold")

    # Ergebniszusammenfassung
    summary = {
        "plan": str(plan_path),
        "applied": bool(created or cron_changed),
        "artifacts": created,
        "cron_changed": cron_changed
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
