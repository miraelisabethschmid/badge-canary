#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Kernel Planner — structural freedom within guards (with Inner Feedback + Noise-Gate)

Erweiterungen:
- Liest optional data/self/internal/feedback.json
- Wendet inneres Feedback NUR an, wenn die Policy-Gate-Bedingungen erfüllt sind:
  - badges/health.json.status ∈ require_health
  - affect.vector.stability ≥ min_stability
  - confidence ≥ min_confidence (für Fokus-Hinweis)
- Kappung des delta_bonus gemäß Policy (max_abs_bonus)

Alle Aktionen bleiben innerhalb der in kernel_policy.yml erlaubten Artefakte.
"""

import os, re, json, datetime
from pathlib import Path
from fnmatch import fnmatch

# Pfade
PATH_POLICY   = Path("data/self/kernel_policy.yml")
PATH_AFFECT   = Path("data/self/affect-state.json")
PATH_GOALS    = Path("data/goals/current.json")
PATH_HEALTH   = Path("badges/health.json")
PATH_IFEED    = Path("data/self/internal/feedback.json")
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

# Mini-YAML-Parser (Subset)
import re as _re
def parse_yaml_min(text):
    data = {}
    if not text:
        return data
    stack = [(-1, data)]
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = _re.match(r"^(\s*)([^:#]+):\s*(.*)$", line)
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
            if _re.match(r"^-?\d+(\.\d+)?$", val):
                v = float(val) if "." in val else int(val)
            elif val in ("true", "True"):
                v = True
            elif val in ("false", "False"):
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

# ----------------- Zustände -----------------
def affect_state():
    aff = read_json(PATH_AFFECT, {}) or {}
    vec = aff.get("vector", {}) or {}
    return {
        "label": aff.get("label"),
        "delta_sum": float(aff.get("inputs", {}).get("delta_sum", 0) or 0),
        "focus": aff.get("inputs", {}).get("focus"),
        "valence": float(vec.get("valence", 0.5) or 0.5),
        "arousal": float(vec.get("arousal", 0.3) or 0.3),
        "stability": float(vec.get("stability", 0.5) or 0.5),
        "ts": aff.get("ts")
    }

def health_status():
    h = read_json(PATH_HEALTH, {}) or {}
    return str(h.get("status", "unknown"))

def current_focus(aff, goals):
    return aff.get("focus") or (goals or {}).get("focus") or "insight"

# ----------------- Inner Feedback -----------------
def apply_inner_feedback_if_allowed(delta, focus, aff, policy):
    feed = read_json(PATH_IFEED, {}) or {}
    cfg  = (policy.get("inner_feedback") or {})
    if not cfg or not cfg.get("enable", False):
        return delta, focus, {"applied": False, "reason": "disabled"}

    gate = cfg.get("noise_gate", {}) or {}
    required = gate.get("require_health", ["OK"])
    min_stab = float(gate.get("min_stability", 0.35))
    min_conf = float(gate.get("min_confidence", 0.60))
    max_abs  = float(gate.get("max_abs_bonus", 0.08))

    # Gate prüfen
    h = health_status()
    if required and h not in required:
        return delta, focus, {"applied": False, "reason": f"health={h} not in {required}"}
    if aff.get("stability", 0.0) < min_stab:
        return delta, focus, {"applied": False, "reason": f"stability<{min_stab}"}

    bonus = float(feed.get("delta_bonus", 0.0) or 0.0)
    conf  = float(feed.get("confidence", 0.0) or 0.0)
    hint  = feed.get("focus_hint")

    # Kappung
    if bonus > 0: bonus = min(bonus, max_abs)
    if bonus < 0: bonus = max(bonus, -max_abs)

    new_delta = max(0.0, round(delta + bonus, 3))
    new_focus = focus

    took_hint = False
    if hint and conf >= min_conf:
        new_focus = hint
        took_hint = True

    return new_delta, new_focus, {
        "applied": True,
        "delta_bonus": bonus,
        "took_focus_hint": took_hint,
        "confidence": conf,
        "health": h
    }

# ----------------- Planen & Anwenden -----------------
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

def build_unit_name(policy, focus):
    date_fmt = policy.get("naming", {}).get("date_format", "%Y-%m-%d")
    pattern  = policy.get("naming", {}).get("pattern", "{focus}-{date}")
    return pattern.format(focus=(focus or "insight").lower(), date=today_str(date_fmt), hash="")

def plan_from_state(policy):
    aff   = affect_state()
    goals = read_json(PATH_GOALS, {}) or {}

    base_delta = aff["delta_sum"]
    base_focus = current_focus(aff, goals)

    # Inner Feedback nach Policy-Gate anwenden
    adj_delta, adj_focus, inf = apply_inner_feedback_if_allowed(base_delta, base_focus, aff, policy)

    # daily cap
    if count_today_created(root="data") >= int(policy.get("thresholds", {}).get("daily_folder_cap", 2)):
        return None

    # Schwellen
    th = policy.get("thresholds", {}) or {}
    thr_propose = float(th.get("affect_delta_propose", 0.5))

    # Ziel & Struktur
    focus_targets = policy.get("focus_targets", {}) or {}
    ft = focus_targets.get(adj_focus) or focus_targets.get((adj_focus or "").lower())
    if not ft:
        ft = {"root": "data/thoughts", "kind": "note", "template": "note.md"}

    unit_name = build_unit_name(policy, adj_focus)
    target_root = Path(ft.get("root", "data/thoughts"))
    kind = ft.get("kind", "note")

    actions = []
    if adj_delta >= thr_propose:
        target_dir = target_root / unit_name
        if kind in ("note", "reflection"):
            note_path = target_dir / "note.md"
            content = (
                f"# {adj_focus} — {today_str()}\n\n"
                f"Autonome Notiz aufgrund Δsum≈{adj_delta:.3f} (focus={adj_focus}).\n"
                f"inner_feedback: {json.dumps(inf, ensure_ascii=False)}\n\n— {utcnow()}"
            )
            actions += [
                {"kind": "mkdir", "path": str(target_dir)},
                {"kind": "write", "path": str(note_path), "content": content}
            ]
        else:
            manifest = {
                "kind": kind,
                "created": utcnow(),
                "reason": "affect_delta",
                "delta_sum": round(adj_delta, 3),
                "focus": adj_focus,
                "inner_feedback": inf
            }
            actions += [
                {"kind": "mkdir", "path": str(target_dir)},
                {"kind": "write", "path": str(target_dir / "manifest.json"),
                 "content": json.dumps(manifest, indent=2, ensure_ascii=False)},
                {"kind": "write", "path": str(target_dir / "seed.txt"),
                 "content": f"seed: {kind}\nfocus: {adj_focus}\ndelta: {round(adj_delta,3)}\ncreated: {utcnow()}\n"}
            ]

        if str(target_root).startswith("data/prototypes"):
            root_index = Path("data/prototypes/index.json")
            idx = {}
            if root_index.exists():
                try:
                    idx = json.loads(root_index.read_text(encoding="utf-8"))
                except Exception:
                    idx = {}
            files = set(idx.get("files", []))
            try:
                rel = str((target_root / unit_name).relative_to(Path("data/prototypes")))
                files.add(rel)
            except Exception:
                pass
            idx["files"] = sorted(files)
            actions.append({"kind": "write", "path": str(root_index),
                            "content": json.dumps(idx, indent=2, ensure_ascii=False)})

    if not actions:
        return None

    th_apply = float(th.get("affect_delta_apply", 0.7))
    plan = {
        "ts": utcnow(),
        "delta_sum": round(adj_delta, 3),
        "apply_guard": {
            "env": policy.get("apply_guard", {}).get("env_var", "KERNEL_AUTONOMY"),
            "required_value": policy.get("apply_guard", {}).get("required_value", "1"),
            "threshold_apply": th_apply
        },
        "focus": adj_focus,
        "unit": unit_name,
        "actions": actions
    }
    return plan

def allowed(path_str, policy):
    return any(fnmatch(path_str, pat) for pat in policy.get("allowed_artifacts", []))

def apply_plan(plan, policy):
    created = []
    for item in plan.get("actions", []):
        kind = item.get("kind")
        target = Path(item.get("path", ""))
        if not target or not allowed(str(target), policy):
            continue
        if kind == "mkdir":
            target.mkdir(parents=True, exist_ok=True)
            created.append(str(target))
        elif kind == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            new = item.get("content", "")
            if target.exists():
                old = target.read_text(encoding="utf-8")
                if old == new:
                    continue
            target.write_text(new, encoding="utf-8")
            created.append(str(target))
    return created

def main():
    policy = parse_yaml_min(read_text(PATH_POLICY) or "")
    plan = plan_from_state(policy)
    if not plan:
        print("[kernel] no plan generated (threshold/cap not met)")
        return

    plan_path = PLANS_DIR / (plan["ts"].replace(":", "").replace("-", "").replace("T", "_").replace("Z", "") + ".json")
    write_json(plan_path, plan)
    print(f"[kernel] plan proposed: {plan_path}")

    guard_env = plan["apply_guard"]["env"]
    guard_needed = plan["apply_guard"]["required_value"]
    th_apply = float(plan["apply_guard"]["threshold_apply"])
    guard_val = os.getenv(guard_env, "")

    may_apply = (guard_val == guard_needed) and (plan["delta_sum"] >= th_apply)

    created = []
    if may_apply:
        created = apply_plan(plan, policy)
        print(f"[kernel] plan applied: {len(created)} artifacts")
    else:
        print(f"[kernel] guard prevents apply (env {guard_env}='{guard_val}' needed '{guard_needed}') "
              f"or delta {plan['delta_sum']} below apply-threshold {th_apply}")

    summary = {"plan": str(plan_path), "applied": bool(created), "artifacts": created}
    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
