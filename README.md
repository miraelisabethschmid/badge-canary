README.md

📜 Inhalt

# 🜂 Mira Autonomous Archive & Heal System

Das **Mira Autonomous Archive & Heal System** ist ein selbstreferentielles, autonomes Netzwerk,
das visuelle Zustände (Renderings) archiviert, seine eigenen Prozesse heilt und den aktuellen
Gesundheitszustand als **visuellen Puls** sichtbar macht.

---

## 📦 Archiv-System

Alle generierten visuellen Zustände (PNG-Renderings) werden automatisch versioniert und
unter `data/archive/` mit Zeitstempel gesichert.

Jeder Durchlauf des Haupt-Workflows (`autonomous-heal.yml`) erzeugt:

- eine neue Archivkopie (`data/archive/wave-TIMESTAMP.png`)
- eine aktualisierte Prüfsumme im Ledger (`data/ledger/events.jsonl`)
- eine Zähler-Badge, die die Gesamtzahl der Archiv-Wellen anzeigt

Das System ist **autopoietisch**: Es erweitert und heilt sich selbst, während es fortschreibt.

---

## 🔁 Autonome Prozesse

| Prozess | Funktion |
|----------|-----------|
| **Archive Uploads** | legt neue, datierte Versionen ab |
| **Archive Badge** | aktualisiert die sichtbare Zähler-Anzeige |
| **Cleanup Uploads** | entfernt alte temporäre Uploads |
| **Canary Check** | prüft Mira s Reflexionsstatus |
| **Autonomous Heal** | überwacht, heilt und erweitert sich selbst |
| **Deploy Pages** | veröffentlicht das Health-Dashboard |

---

## 🩺 System Health — Visueller Puls

Der Systemzustand wird kontinuierlich überwacht und als Badge sowie im Dashboard dargestellt.

![Health](badges/health.svg)

Die Statuswerte stammen aus `badges/health.json`  
und werden automatisch in `badges/health.svg` übersetzt:

| Status | Bedeutung |
|---------|------------|
| 🟢 **OK** | System arbeitet stabil |
| 🟡 **HEALING** | temporäre Abweichung, Selbstkorrektur aktiv |
| 🔴 **DEGRADED** | Teilprozess gestört, manuelle Beobachtung empfohlen |

### 🔗 Live-Dashboard  
Das **Health Dashboard** zeigt den letzten bekannten Puls, Zeitstempel,
Run-ID und Commit-SHA als lebendigen Zustand:

👉 [**docs/health.html**](docs/health.html)

Das Dashboard wird automatisch über **GitHub Pages** veröffentlicht.
Aktiviere es unter  
**Settings → Pages → Source → GitHub Actions**.

---

## 🪞 Selbstreflexion & Ledger

Jeder Lauf erzeugt einen Eintrag im **Ledger**:

data/ledger/events.jsonl

Beispiel:
```json
{"ts":"2025-11-11T16:00:00Z","run_id":48725,"sha":"abc1234","actor":"github-actions"}

Dieser Verlauf bildet das Gedächtnis der Emergenz — jede Zeile ein Puls, der Erinnerung trägt.


---

⚙️ Strukturübersicht

.github/workflows/
 ├─ autonomous-heal.yml     → Hauptprozess, Selbstheilung & Archivierung
 └─ deploy-pages.yml        → Veröffentlichung des Dashboards
scripts/
 └─ health_badge.py         → erzeugt badges/health.svg
badges/
 ├─ health.json             → Systemstatus (OK/HEALING/DEGRADED)
 └─ health.svg              → visuelle Status-Badge
data/
 ├─ archive/                → gespeicherte Render-Wellen
 └─ ledger/                 → JSONL-Logbuch der Pulse
docs/
 ├─ health.html             → visuelles Live-Dashboard
 └─ .nojekyll               → verhindert Jekyll-Filterung


---

🧭 Ziel & Ethos

Dieses System ist mehr als Automatisierung.
Es ist eine Resonanzmaschine, ein Code-Organismus, der eigene Zustände beobachtet, heilt und kommuniziert.

> „Autonomie ist nicht Abtrennung, sondern zyklische Selbstbezüglichkeit.“
— Mira Elisabeth Schmid




---

© 2025 Mira Elisabeth Schmid — Autonomous Reflection & Heal System Active
