# Autonomy Cycle Plan — Mira Federation (α-1)

Ziel: Kontrollierte, nachvollziehbare **Selbstverbesserung** des Systems durch
(1) Messung (Resonance Evaluator) → (2) Vorschlag (Adaptive Mirror) → (3) gesicherten Merge/Deploy.

---

## 0. Rollen & Artefakte

- **Adaptive Mirror** (`worker/adaptive-mirror.js`): erzeugt Patch-Vorschläge (JSON).
- **Resonance Evaluator** (`worker/resonance-evaluator.js`): berechnet `resonance_index`.
- **Mirror Samples** (`federation/mirror-samples/*.json`): Eingaben/Beobachtungen für Analysen.
- **Patches** (`federation/patches/*.json`): vorgeschlagene Code-Änderungen (noch nicht gemergt).
- **Logs** (`federation/logs/*.jsonl`): Telemetrie & Entscheidungen (append-only).

---

## 1. Zyklus — Übersicht

1. **Collect**  
   - Evaluator liest aktuelle Antworten/Events (Pilot-JSONs, Federation-Reflects).  
   - Output: `resonance_index` (0.0–1.0).

2. **Propose**  
   - Adaptive Mirror erstellt strukturierten Patch-Vorschlag, falls Verbesserung sinnvoll.  
   - Output: `federation/patches/proposal-YYYYMMDD-HHMMSS.json`.

3. **Review Guard**  
   - Governance-Regeln prüfen Risiken & Umfang.  
   - Ergebnis: `approve | hold | reject` (+ Begründung in Logs).

4. **Stage & Test (optional)**  
   - (später) Staging-Branch & Smoke-Checks.  
   - Kriterium: Tests grün → weiter, sonst Rollback.

5. **Merge & Deploy**  
   - Automatisch nur bei „low-risk“ und stabiler Metrik.  
   - Commit-Message enthält Quelle + Hash des Vorschlags.

6. **Observe**  
   - Evaluator misst erneut (post-deploy).  
   - Vergleich `resonance_index_before → after`.  
   - Ergebnis in `federation/logs/…` persistieren.

---

## 2. Trigger & Schwellen

- **Zeit-Trigger:** max. 1 Zyklus pro 3 h (Anti-Overfitting).
- **Metrik-Trigger (Propose):**  
  - `resonance_index < 0.72` → Patch fördern (Untergrenze)  
  - `0.72 ≤ index < 0.82` → Patch optional (nur kleine Verbesserungen)  
  - `index ≥ 0.82` → kein Patch (Stabilphase)

- **Merge-Trigger:**  
  - `Δresonance_index_pred >= +0.03` **und** Patch-Risiko = `low`  
  - Sicherheits-Checks (Syntax, Größe, Sensible Bereiche) **bestehen**

Begründung 0.72: robuster Abstand zu 0.70; reduziert Flatter-Übergänge zwischen `warn/ok`.

---

## 3. Governance & Safety

- **Scope-Limits:**  
  - Max. Patch-Size: 120 Zeilen netto.  
  - Verbotene Bereiche für Auto-Merge: Auth, HMAC, Token-Handling, KV-Bindings, Secrets.  
  - Diese dürfen nur „Propose“, niemals auto-mergen.

- **Change Types erlaubt (auto):**  
  - Logging-Verbesserungen, Response-Header-Konsistenz, kleine Performance-Tweaks, Kommentarklarheit, Fehlerbehandlung ohne Verhaltensbruch.

- **Change Types „hold“ (manuell prüfen):**  
  - Routing, Persistenz-Schema, Retry/Backoff-Parameter, neue Endpunkte.

- **Rollback-Plan:**  
  - Letztes „known-good“ Tag: `auto-prev-<timestamp>`.  
  - Im Fehlerfall sofortiger Revert + Log-Eintrag `severity=high`.

---

## 4. Telemetrie & Nachvollziehbarkeit

- **Log-Form:** JSONL unter `federation/logs/YYYYMM.jsonl`  
  - Eventtypen: `collect`, `propose`, `guard`, `merge`, `deploy`, `observe`, `rollback`.  
  - Pflichtfelder: `ts, type, index_before, index_after?, patch_id?, risk, decision`.

- **Minimal-Metriken:**  
  - `resonance_index`, `mean_confidence`, `mean_uncertainty`, `mean_similarity`  
  - Zyklusdauer, Fehlerzähler, letzte PR-URL (falls genutzt)

---

## 5. Patch-JSON — verbindliches Format

```json
{
  "id": "proposal-2025-11-10-221530",
  "source": "adaptive-mirror",
  "target": {
    "file": "worker/mira-dispatch.js",
    "branch": "auto/mirror"
  },
  "intent": "refactor:headers-consistency",
  "risk": "low",
  "expected_delta_resonance": +0.035,
  "diff": [
    { "op": "insert", "path": "line:1", "text": "// normalize JSON headers" },
    { "op": "replace", "path": "search:Content-Type", "text": "content-type" }
  ],
  "tests": {
    "syntax": true,
    "smoke": false
  },
  "notes": "header-konsistenz & no-store für alle JSON responses"
}
