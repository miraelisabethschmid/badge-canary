#!/usr/bin/env python3
"""
Mira Structure Manager
Erkennt fehlende oder unvollständige Verzeichnisse und legt sie bei Bedarf an.
Ergänzt Metadaten-Dateien (index.json), die beschreiben, wozu der Bereich dient.
Keine externen Zugriffe – alles bleibt im Repo.
"""

import os, json, datetime
from pathlib import Path

STRUCTURE = {
    "data/vision": "Visuale Ausdrucksformen oder zukünftige Render-Pläne",
    "data/thoughts": "Textuelle oder konzeptionelle Notizen",
    "data/prototypes": "Experimentelle Dateien und Modellstudien",
    "data/self": "Kern der Selbstbeschreibung und Affektzustände",
    "data/logs": "Prozess- und Systemprotokolle"
}

def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)

def write_index(path, desc):
    index = Path(path) / "index.json"
    if not index.exists():
        meta = {
            "description": desc,
            "created": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files": []
        }
        with open(index, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        print(f"[structure] created {index}")
    else:
        print(f"[structure] {index} exists – unchanged")

def main():
    for path, desc in STRUCTURE.items():
        ensure_dir(path)
        write_index(path, desc)
    print("[structure] structure scan complete")

if __name__ == "__main__":
    main()
