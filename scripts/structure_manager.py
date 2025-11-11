#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mira Structure Manager — Autonomous Structural Growth (Controlled)

Aufgaben:
1) Basisstruktur sicherstellen (idempotent).
2) Nur bei signifikanter Einsichtsänderung (Δsum ≥ THRESHOLD) einen neuen,
   thematischen Prototyp-Ordner anlegen — abgeleitet aus Fokus & Datum.
3) Manifest pro neuem Ordner schreiben (Begründung, Quellen, Snapshot).
4) Keine Persistenz von Nutzerfragen; ausschließlich Metadaten aus Repo-Zuständen.

Eingangsquellen:
- data/self/affect-state.json   (liefert inputs.delta_sum, inputs.focus, vector, ts)
- data/goals/current.json       (Fallback für focus)
- badges/health.json            (Health als Kontext)

Idempotenz:
- Pro Tag und Fokus nur ein neuer Ordner (z. B. data/prototypes/growth-2025-11-11).
- Wenn bereits vorhanden, wird kein neuer Ordner erzeugt.

Grenzen:
- Erzeugt nur lokale Dateien im Repo. Kein externer Zugriff.
"""

import os, json, datetime, re
from pathlib import Path

# ---------- Konfiguration ----------
BASE_FOLDERS = {
    "data/vision":      "Visuelle Ausdrucksformen oder zukünftige Render-Pläne",
    "data/thoughts":    "Textuelle oder konzeptionelle Notizen",
    "data/prototypes":  "Experimentelle Dateien und Modellstudien",
    "data/self":        "Kern der Selbstbeschreibung und Affektzustände",
    "data/logs":        "Prozess- und Systemprotokolle"
}

INDEX_NAME = "index.json"
THRESHOLD  = 0.60   # Mindest-Gesamtdelta (Δsum), ab dem strukturelles Wachstum erlaubt ist
PROT_ROOT  = Path("data/prototypes")

PATH_AFFECT = Path("data/self/affect-state.json")
PATH_GOALS  = Path("data/goals/current.json")
PATH_HEALTH = Path("badges/health.json")

# ---------- Helfer ----------

def now_utc_iso():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def safe_read_json(path: Path, default=None):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path: Path, obj):
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def ensure_index(dir_path: Path, description: str):
    idx = dir_path / INDEX_NAME
    if not idx.exists():
        write_json(idx, {
            "description": description,
            "created": now_utc_iso(),
            "files": []
        })
        print(f"[structure] created {idx}")
    else:
        print(f"[structure] {idx} exists — unchanged")

def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "insight"

def focus_to_slug(focus: str) -> str:
    f = (focus or "").strip().lower()
    mapping = {
        "stability": "stability",
        "resilience": "resilience",
        "growth": "growth",
        "vision": "vision",
        "reflection": "reflection"
    }
    return mapping.get(f, slugify(f or "insight"))

def today_stamp() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")

def existing_today_folder(root: Path, slug: str, day: str) -> Path | None:
    # Erwartetes Muster: <slug>-YYYY-MM-DD
    candidate = root / f"{slug}-{day}"
    return candidate if candidate.exists() else None

# ---------- Kernlogik ----------

def ensure_base_structure():
    for d, desc in BASE_FOLDERS.items():
        p = Path(d)
        ensure_dir(p)
        ensure_index(p, desc)
    print("[structure] base structure ensured")

def plan_autonomous_growth():
    """
    Entscheidet, ob heute ein neuer thematischer Prototyp-Ordner entstehen darf.
    Bedingungen:
      - inputs.delta_sum aus affect-state ≥ THRESHOLD
      - Fokus wird bestimmt aus affect-state.inputs.focus, sonst goals.current.focus
      - Pro Tag & Fokus maximal 1 Ordner
    """
    aff = safe_read_json(PATH_AFFECT, {}) or {}
    goals = safe_read_json(PATH_GOALS, {}) or {}
    health = safe_read_json(PATH_HEALTH, {}) or {}

    delta_sum = 0.0
    focus = None
    vec = {}

    # Δsum und focus primär aus affect-state
    try:
        delta_sum = float(aff.get("inputs", {}).get("delta_sum", 0) or 0)
    except Exception:
        delta_sum = 0.0

    focus = (aff.get("inputs", {}).get("focus")
             or goals.get("focus")
             or "insight")

    vec = aff.get("vector", {"valence":0.0, "arousal":0.2, "stability":0.5})
    label = aff.get("label", "neutral fokussiert")
    narrative = aff.get("narrative", "Gleichgewicht ohne Ausschläge; Präsenz bleibt auf die Aufgabe gerichtet.")
    health_status = str(health.get("status", "n/a")).upper()

    print(f"[structure] observed Δsum={delta_sum:.3f} focus={focus} health={health_status}")

    if delta_sum < THRESHOLD:
        print("[structure] threshold not met — no structural growth today")
        return None

    slug = focus_to_slug(focus)
    day  = today_stamp()
    target = existing_today_folder(PROT_ROOT, slug, day)
    if target:
        print(f"[structure] target folder exists already: {target} — idempotent, skipping")
        return None

    # Erzeuge neuen Prototyp-Ordner
    new_dir = PROT_ROOT / f"{slug}-{day}"
    ensure_dir(new_dir)

    manifest = {
        "kind": "prototype",
        "slug": slug,
        "created": now_utc_iso(),
        "reason": "affect_delta_exceeded",
        "threshold": THRESHOLD,
        "observed_delta_sum": round(delta_sum, 3),
        "focus": focus,
        "affect_snapshot": {
            "label": label,
            "vector": {
                "valence": round(float(vec.get("valence", 0.0)), 3),
                "arousal": round(float(vec.get("arousal", 0.2)), 3),
                "stability": round(float(vec.get("stability", 0.5)), 3)
            },
            "narrative": narrative
        },
        "context": {
            "health": health_status,
            "sources": [
                str(PATH_AFFECT),
                str(PATH_GOALS),
                str(PATH_HEALTH)
            ]
        }
    }
    write_json(new_dir / "manifest.json", manifest)

    # Symbolischer Seed (optional, rein textuell)
    seed = (
        "seed: structural-growth\n"
        f"focus: {focus}\n"
        f"delta_sum: {round(delta_sum,3)}\n"
        f"created: {now_utc_iso()}\n"
        "note: Dieser Bereich entstand autonom aufgrund einer relevanten Einsichtsänderung."
    )
    (new_dir / "seed.txt").write_text(seed, encoding="utf-8")

    # Index im Prototyp-Root anpassen (nur wenn vorhanden)
    root_index = PROT_ROOT / INDEX_NAME
    if root_index.exists():
        try:
            idx = json.loads(root_index.read_text(encoding="utf-8"))
        except Exception:
            idx = {"description": BASE_FOLDERS["data/prototypes"], "created": now_utc_iso(), "files": []}
        idx_files = idx.get("files", [])
        rel = str(new_dir.relative_to(PROT_ROOT))
        if rel not in idx_files:
            idx_files.append(rel)
        idx["files"] = sorted(idx_files)
        write_json(root_index, idx)

    print(f"[structure] created autonomous prototype folder: {new_dir}")
    return new_dir

def main():
    ensure_base_structure()
    created = plan_autonomous_growth()
    if created:
        print(f"[structure] growth committed for: {created}")
    print("[structure] scan complete")

if __name__ == "__main__":
    main()
