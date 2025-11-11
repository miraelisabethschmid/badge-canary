#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Health Updater
- Liest Repository-Zustand
- Leitet Status OK / HEALING / DEGRADED ab
- Schreibt badges/health.json
- Rendert badges/health.svg (minimaler, libfreier Badge)
"""

from __future__ import annotations
import json, os, time
from datetime import datetime, timezone

# ---- Konfiguration ----------------------------------------------------------
CHECKS = {
    # Datei -> (ist_erforderlich, min_bytes)
    "data/self/self-describe.json": (True, 16),
    "data/voice/voice_of_day.json": (True, 16),
    "data/voice/audio/latest.mp3":  (False, 1),
    "docs/index.html":              (True, 16),
}
LEDGER = "data/ledger/events.jsonl"
HEALTH_JSON = "badges/health.json"
HEALTH_SVG  = "badges/health.svg"

# Statusfarben für SVG (rechts)
COLOR = {
    "OK":       "#2e7d32",  # green 800
    "HEALING":  "#f9a825",  # amber 700
    "DEGRADED": "#c62828",  # red 800
}

# ---- Hilfen -----------------------------------------------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def file_ok(path: str, min_bytes: int) -> bool:
    try:
        return os.path.getsize(path) >= min_bytes
    except FileNotFoundError:
        return False

def last_ledger_ts(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        if not lines:
            return None
        entry = json.loads(lines[-1])
        return entry.get("ts") or entry.get("timestamp")
    except Exception:
        return None

def decide_status() -> str:
    # 1) Pflichtdateien vorhanden?
    required_ok = True
    any_missing = False
    for p, (required, minb) in CHECKS.items():
        ok = file_ok(p, minb)
        if required and not ok:
            required_ok = False
        if not ok:
            any_missing = True

    # 2) Ledger-Aktivität (optional, erhöht Vertrauen)
    last_ts = last_ledger_ts(LEDGER)
    recently_active = False
    if last_ts:
        try:
            dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - dt
            # Aktiv in den letzten 24h?
            recently_active = delta.total_seconds() <= 24 * 3600
        except Exception:
            pass

    # Logik:
    # - Wenn Pflicht fehlt -> DEGRADED
    # - Wenn Pflicht ok, aber sonst etwas fehlt ODER keine Aktivität -> HEALING
    # - Sonst OK
    if not required_ok:
        return "DEGRADED"
    if any_missing or not recently_active:
        return "HEALING"
    return "OK"

def write_json(status: str):
    os.makedirs(os.path.dirname(HEALTH_JSON), exist_ok=True)
    data = {"status": status, "ts": utc_now_iso()}
    with open(HEALTH_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data

def render_badge(status: str):
    left_text  = "health"
    right_text = status
    left_w     = 60
    right_w    = 54 if len(right_text) < 6 else 7 * len(right_text) + 10
    width      = left_w + right_w
    color_right = COLOR.get(status, COLOR["DEGRADED"])
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" aria-label="{left_text}: {right_text}">
  <linearGradient id="g" x2="0" y2="100%">
    <stop offset="0%"  stop-color="#fff" stop-opacity=".7"/>
    <stop offset="100%" stop-opacity=".7"/>
  </linearGradient>
  <mask id="r"><rect width="{width}" height="20" rx="3" fill="#fff"/></mask>
  <g mask="url(#r)">
    <rect width="{left_w}" height="20" fill="#555"/>
    <rect x="{left_w}" width="{right_w}" height="20" fill="{color_right}"/>
    <rect width="{width}" height="20" fill="url(#g)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{left_w/2}" y="14">{left_text}</text>
  </g>
  <g fill="#000" opacity=".9" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{left_w + right_w/2}" y="14">{right_text}</text>
  </g>
</svg>"""
    os.makedirs(os.path.dirname(HEALTH_SVG), exist_ok=True)
    with open(HEALTH_SVG, "w", encoding="utf-8") as f:
        f.write(svg)

def main():
    status = decide_status()
    data = write_json(status)
    render_badge(status)
    print(f"[health] status={data['status']} ts={data['ts']}")

if __name__ == "__main__":
    main()
