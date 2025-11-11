#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Kernel Planner — structural freedom within guards (with Inner Feedback)

Erweiterungen:
- Liest optional data/self/internal/feedback.json
- Additiver, gedeckelter delta_bonus (±0.08) auf affect_delta
- Optionaler focus_hint (mit confidence-Grenze) überschreibt Fokus
- Alles bleibt idempotent & innerhalb der bestehenden Guards/Whitelist

Hinweis: Policy/Whitelist/Guards wie gehabt in data/self/kernel_policy.yml
"""

import os, re, json, datetime, glob
from pathlib import Path

# Pfade
PATH_POLICY   = Path("data/self/kernel_policy.yml")
PATH_AFFECT   = Path("data/self/affect-state.json")
PATH_GOALS    = Path("data/goals/current.json")
PATH_HEALTH   = Path("badges/health.json")
PATH_IFEED    = Path("data/self/internal/feedback.json")  # NEU (optional)
PLANS_DIR     = Path("data/kernel/plans")

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

# Mini-YAML-Parser (Subset) ------------------------------
import re as _re
def parse_yaml_min(text):
    data = {}
    if not text:
        return data
    stack = [(-1, data)]
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"): continue
        m = _re.match(r"^(\s*)([^:#]+):\s*(.*)$", line)
        if not m: continue
        ind, key, val = len(m.group(1).expandtabs(2)), m.group(2).strip(), m.group(3).strip()
        while stack and ind <= stack[-1][0]: stack.pop()
        parent = stack[-1][1] if stack else data
        if val == "":
            parent[key] = {}; stack.append((ind, parent[key]))
        else:
            if _re.match(r"^-?\d+(\.\d+)?$", val): v = float(val) if "." in val else int(val)
            elif val in ("true","True"): v = True
            elif val in ("false","False"): v = False
            elif val.startswith("[") and val.endswith("]"):
                try: v = json.loads(val.replace("'", '"'))
                except Exception: v = val
            else: v = val.strip('"\'')
            parent[key] = v
    return data

# --------------------------------------------------------

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

def influence_from_inner_feedback(delta, focus):
    """Wendet vorsichtiges internes Feedback an (falls vorhanden)."""
    feed = read_json(PATH_IFEED, {}) or {}
    bonus = float(feed.get("delta_bonus", 0.0) or 0.0)
    hint  = feed.get("focus_hint")
    conf  = float(feed.get("confidence", 0.0) or 0.0)

    # Delta-Bonus begrenzen gemäß Guard
    bonus_cap = float((feed.get("guard") or {}).get("max_abs_bonus", 0.08))
    if bonus > 0: bonus = min(bonus, bonus_cap)
    if bonus < 0: bonus = max(bonus, -bonus_cap)

    new_delta = max(0.0, round(delta + bonus, 3))

    # Fokus-Übernahme nur bei hinreichender confidence
    new_focus = focus
    if hint and conf >= 0.6:
        new_focus = hint

    return new_delta, new_focus, {"applied_bonus": bonus, "took_focus_hint": (new_focus != focus), "confidence": conf}

def plan_from_state(policy):
    delta = affect_delta()
    focus = current_focus()

    # Inner Feedback (optional) einbeziehen
    delta, focus, inf = influence_from_inner_feedback(delta, focus)

    date_fmt = policy.get("naming", {}).get("date_format", "%Y-%m-%d")
    name_pat = policy.get("naming", {}).get("pattern", "{focus}-{date}")
    date_str = today_str(date_fmt)
    slug = (focus or "insight").lower()
    unit_name = name_pat.format(focus=slug, date=date_str, hash="")  # hash wird ggf. in Policy ergänzt

    # daily cap
    if count_today_created(root="data", date_str=date_str) >= int(policy.get("thresholds",{}).get("daily_folder_cap", 2)):
        return None

    ft = policy.get("focus_targets", {}).get(slug) or policy.get("focus_targets", {}).get(focus) \
         or {"root":"data/thoughts","kind":"note","template":"note.md"}
    root = Path(ft.get("root","data/thoughts"))
    kind = ft.get("kind","note")

    target_dir = root / unit_name
    actions = []

    # Propose
    if delta >= float(policy.get("thresholds",{}).get("affect_delta_propose", 0.5)):
        if kind in ("note","reflection"):
            note_path = target_dir / "note.md"
            content = f"# {slug} — {date_str}\n\nAutonome Notiz aufgrund Δsum≈{delta:.3f} (focus={focus}).\n\n— {utcnow()}"
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
                "focus": focus,
                "inner_feedback": inf
            }
            actions += [
                {"kind":"mkdir","path":str(target_dir)},
                {"kind":"write","path":str(target_dir / "manifest.json"), "content": json.dumps(manifest, indent=2, ensure_ascii=False)},
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

def apply_plan(plan, policy):
    from fnmatch import fnmatch
    def allowed(path_str):
        return any(fnmatch(path_str, pat) for pat in policy.get("allowed_artifacts", []))

    created = []
    for item in plan.get("actions", []):
        kind = item.get("kind")
        target = Path(item.get("path",""))
        if not target:
            continue
        if not allowed(str(target)):
            print(f"[kernel] skip (not allowed): {target}")
            continue
        if kind == "mkdir":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.mkdir(parents=True, exist_ok=True)
            created.append(str(target))
        elif kind == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            new = item.get("content","")
            if target.exists():
                old = target.read_text(encoding="utf-8")
                if old == new: 
                    continue
            target.write_text(new, encoding="utf-8")
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
    if not cfg or not cfg.get("enable"): return []
    changed = []
    for tgt in cfg.get("targets", []):
        f = Path(tgt.get("file",""))
        if not f.exists(): continue
        y = f.read_text(encoding="utf-8")
        m = re.search(r"cron:\s*'(\S+)'", y)
        if not m: continue
        expr = m.group(1)
        minutes = None
        if expr.startswith("*/"):
            try: minutes = int(expr.split()[0].replace("*/",""))
            except Exception: minutes = None
        elif expr.startswith("0 "):
            minutes = 60
        if minutes is None: continue
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

def main():
    policy = parse_yaml_min(read_text(PATH_POLICY) or "")
    delta = affect_delta()

    plan = plan_from_state(policy)
    if not plan:
        print("[kernel] no plan generated (threshold/cap not met)")
        return

    plan_path = PLANS_DIR / (plan["ts"].replace(":","").replace("-","").replace("T","_").replace("Z","") + ".json")
    write_json(plan_path, plan)
    print(f"[kernel] plan proposed: {plan_path}")

    guard_env = plan["apply_guard"]["env"]
    guard_needed = plan["apply_guard"]["required_value"]
    guard_val = os.getenv(guard_env, "")
    may_apply = (guard_val == guard_needed) and (delta >= float(parse_yaml_min(read_text(PATH_POLICY) or "").get("thresholds",{}).get("affect_delta_apply",0.7)))

    created = []
    cron_changed = []
    if may_apply:
        created = apply_plan(plan, policy)
        if policy.get("cron_adjustments",{}).get("enable"):
            cron_changed = adjust_cron(policy)
        print(f"[kernel] plan applied: {len(created)} artifacts, cron_changed={len(cron_changed)}")
    else:
        print(f"[kernel] guard prevents apply (env {guard_env}='{guard_val}' needed '{guard_needed}') or delta below apply-threshold")

    summary = {"plan": str(plan_path), "applied": bool(created or cron_changed), "artifacts": created, "cron_changed": cron_changed}
    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
