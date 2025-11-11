#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Erzeugt einen Index der neuesten Kernel-Pläne für die Website:
- Liest data/kernel/plans/*.json
- Sortiert nach Zeitstempel (neu → alt)
- Schreibt data/kernel/plans/index.json mit den letzten N Einträgen
- Idempotent, keine externen Abhängigkeiten
"""

import json, re
from pathlib import Path
from datetime import datetime

PLANS_DIR = Path("data/kernel/plans")
OUT_FILE  = PLANS_DIR / "index.json"
LIMIT     = 50  # Anzahl der Einträge für das Dashboard

def parse_ts(ts: str) -> datetime | None:
    if not ts:
        return None
    # erwartet "YYYY-MM-DDTHH:MM:SSZ"
    ts = ts.strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(ts, fmt)
        except Exception:
            continue
    return None

def main():
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for f in sorted(PLANS_DIR.glob("*.json")):
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        ts = obj.get("ts") or ""
        dt = parse_ts(ts)
        items.append({
            "file": f.name,
            "ts": ts,
            "delta_sum": obj.get("delta_sum", 0),
            "focus": obj.get("focus") or "",
            "unit": obj.get("unit") or "",
            "applied": bool(obj.get("actions"))
        })
    # neueste zuerst
    items.sort(key=lambda x: (x["ts"] or ""), reverse=True)
    data = {
        "updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(items),
        "files": [i["file"] for i in items[:LIMIT]],
        "entries": items[:LIMIT]
    }
    OUT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[plans-index] wrote {OUT_FILE} with {min(len(items), LIMIT)} entries")

if __name__ == "__main__":
    from datetime import datetime
    main()
