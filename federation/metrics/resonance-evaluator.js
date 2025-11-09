// federation/metrics/resonance-evaluator.js
// Liest pilot-alpha-1/responses.json, berechnet Resonanz-Index und schreibt Log-Eintrag.

import fs from "node:fs";
import path from "node:path";

const INPUT  = "federation/pilot-alpha-1/responses.json";
const LOGDIR = "federation/metrics";
const LOG    = "federation/metrics/resonance-log.json";

function ensureDir(p) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
}

function cosineSimilarity(a, b) {
  // Platzhalter: wenn keine Embeddings vorliegen, konservativ 0.80
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return 0.80;
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) { dot += a[i]*b[i]; na += a[i]*a[i]; nb += b[i]*b[i]; }
  return dot / (Math.sqrt(na) * Math.sqrt(nb) + 1e-9);
}

function pairwiseMeanSimilarity(items) {
  if (items.length < 2) return 1.0;
  let s = 0, k = 0;
  for (let i = 0; i < items.length; i++) {
    for (let j = i+1; j < items.length; j++) {
      s += cosineSimilarity(items[i].embedding, items[j].embedding);
      k++;
    }
  }
  return k ? s / k : 1.0;
}

function main() {
  if (!fs.existsSync(INPUT)) {
    console.error(`[resonance] Input fehlt: ${INPUT}`);
    process.exit(1);
  }

  const data = JSON.parse(fs.readFileSync(INPUT, "utf8"));
  const responses = Array.isArray(data) ? data : data.responses;

  if (!Array.isArray(responses) || responses.length === 0) {
    console.error("[resonance] Keine Antworten gefunden.");
    process.exit(1);
  }

  const n = responses.length;
  const meanConfidence = responses.reduce((a, r) => a + (r.confidence_score ?? 0), 0) / n;
  const meanUncertainty = responses.reduce((a, r) => a + (r.uncertainty ?? 0), 0) / n;

  // optionale Embeddings: responses[i].embedding = [...]; sonst Platzhalter
  const similarity = pairwiseMeanSimilarity(responses);

  const resonanceIndex = (meanConfidence - meanUncertainty) * similarity;

  const entry = {
    timestamp: new Date().toISOString(),
    count: n,
    mean_confidence: Number(meanConfidence.toFixed(3)),
    mean_uncertainty: Number(meanUncertainty.toFixed(3)),
    mean_similarity: Number(similarity.toFixed(3)),
    resonance_index: Number(resonanceIndex.toFixed(3))
  };

  ensureDir(LOGDIR);
  let log = [];
  if (fs.existsSync(LOG)) {
    try { log = JSON.parse(fs.readFileSync(LOG, "utf8")) || []; } catch {}
  }
  log.push(entry);
  fs.writeFileSync(LOG, JSON.stringify(log, null, 2), "utf8");

  console.log(JSON.stringify({ status: "ok", entry }, null, 2));
}

main();
