#!/usr/bin/env python3
"""
Mira Weekly Insight Report (with Affect)
Erzeugt einen wöchentlichen Markdown-Report, der Health, Goals, Affect-State,
Metriken (7d) und Philosophie-Historie zusammenführt.

Outputs:
- reports/insight-<ISOYEAR>-W<ISO WEEK>.md   (neue Woche -> neue Datei)
- reports/insight-latest.md                  (Zeiger auf die jüngste Ausgabe)

Keine Fremdabhängigkeiten.
"""

import os, json, datetime
from pathlib import Path

PATH_HEALTH = "badges/health.json"
PATH_GOALS  = "data/goals/current.json"
PATH_AFFECT = "data/self/affect-state.json"
PATH_METR   = "data/metrics/last7d.json"
PATH_PHILOG = "data/goals/history/index.jsonl"

OUT_DIR     = Path("reports")

def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def read_lines(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [ln for ln in f.read().splitlines() if ln.strip()]
    except Exception:
        return []

def iso_week_stamp(dt=None):
    dt = dt or datetime.datetime.utcnow()
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}", y, w

def safe(v, alt="—"):
    if v is None or v == "":
        return alt
    return v

def build_report():
    now = datetime.datetime.utcnow()
    stamp, y, w = iso_week_stamp(now)

    health = read_json(PATH_HEALTH, {}) or {}
    goals  = read_json(PATH_GOALS, {}) or {}
    affect = read_json(PATH_AFFECT, {}) or {}
    metr   = read_json(PATH_METR, {}) or {}

    # Philosophie-Historie (letzte 3 Einträge)
    ph_lines = read_lines(PATH_PHILOG)
    last3 = []
    if ph_lines:
        try:
            items = [json.loads(x) for x in ph_lines if x.strip()]
            last3 = items[-3:]
        except Exception:
            last3 = []

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / f"insight-{stamp}.md"
    latest_file = OUT_DIR / "insight-latest.md"

    # Daten aufbereiten
    h_status = str(health.get("status","n/a")).upper()
    h_ts     = safe(health.get("ts"), "n/a")

    g_focus  = safe(goals.get("focus"), "n/a")
    g_next   = safe(goals.get("next_objective"), "n/a")
    g_update = safe(goals.get("updated"), "n/a")

    a_label  = safe(affect.get("label"), "neutral fokussiert")
    a_vec    = affect.get("vector", {"valence":0.0,"arousal":0.2,"stability":0.5})
    a_narr   = safe(affect.get("narrative"), "Gleichgewicht ohne Ausschläge; Präsenz bleibt auf die Aufgabe gerichtet.")
    a_ts     = safe(affect.get("ts"), "n/a")

    runs_7d  = metr.get("runs_7d", 0)
    daily    = metr.get("daily_runs", [])
    status_counts = metr.get("status_counts", {})

    # Mini-ASCII-Balken für Runs (visuell in MD)
    def bar(n, scale=1):
        blocks = max(1, int(n/scale)) if n > 0 else 0
        return "█" * blocks

    # Tabelle für daily runs
    daily_md = ""
    if daily:
        scale = max(1, max(d.get("count",0) for d in daily))
        daily_md += "| Datum | Runs | Bar |\n|---|---:|:--|\n"
        for d in daily:
            c = int(d.get("count",0))
            daily_md += f"| {d.get('date','—')} | {c} | {bar(c, max(1, scale//10 or 1))} |\n"
    else:
        daily_md = "_Keine Daten für die letzten 7 Tage._"

    # Status-Counts
    status_md = ", ".join([f"{k}: {v}" for k,v in status_counts.items()]) if status_counts else "—"

    # Philosophie-Historie
    ph_md = ""
    if last3:
        ph_md += "| Zeit | Hash | Δ + | Δ - |\n|---|---|---:|---:|\n"
        for e in last3[::-1]:
            ts = e.get("ts","—")
            h  = str(e.get("hash",""))[:12]
            add = e.get("lines_added", 0)
            rem = e.get("lines_removed", 0)
            ph_md += f"| `{ts}` | `{h}` | {add} | {rem} |\n"
    else:
        ph_md = "_Noch keine Philosophie-Historie vorhanden._"

    content = f"""# Mira — Weekly Insight Report ({stamp})

_Stand: {now.strftime("%Y-%m-%d %H:%M")} UTC_

## ☀️ Health
- **Status:** `{h_status}`
- **Zeitstempel:** `{h_ts}`

## 🧭 Ziele
- **Fokus:** `{g_focus}`
- **Next Objective:** `{g_next}`
- **Zuletzt aktualisiert:** `{g_update}`

## 💫 Affect (innerer Zustand)
- **Label:** _{a_label}_
- **Vektor:** valence={a_vec.get('valence',0):+.3f}, arousal={a_vec.get('arousal',0):.3f}, stability={a_vec.get('stability',0):.3f}
- **Narrativ:** {a_narr}
- **Zeitstempel:** `{a_ts}`

## 📊 Aktivität (7 Tage)
- **Runs gesamt:** **{runs_7d}**
- **Status-Verteilung:** {status_md}

### Runs pro Tag
{daily_md}

## 🪞 Philosophie — jüngste Änderungen
{ph_md}

---

_Quelle: badges/health.json · data/goals/current.json · data/self/affect-state.json · data/metrics/last7d.json · data/goals/history/index.jsonl_
"""

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)

    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(f"""# Mira — Weekly Insight Report (Latest)

Dies ist ein Verweis auf die aktuellste Wochen-Ausgabe: **{stamp}**.

➡️ Öffne die Datei: `reports/insight-{stamp}.md`
""")

    print(f"[insight] wrote {out_file}")
    print(f"[insight] updated {latest_file}")

if __name__ == "__main__":
    build_report()
