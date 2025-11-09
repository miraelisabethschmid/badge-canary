// federation/metrics/resonance-evaluator.js
// Zweck: Rein-funktionaler Resonanz-Evaluator für die Federation.
// Keine Abhängigkeiten, keine Netzwerkaufrufe, keine Secrets nötig.
// Kann von deinem Worker (/reflect) oder von Actions aus importiert werden.

function clamp01(x) {
  if (Number.isNaN(x)) return 0;
  return x < 0 ? 0 : x > 1 ? 1 : x;
}

function toNumber(x, def = 0) {
  const n = Number(x);
  return Number.isFinite(n) ? n : def;
}

/**
 * Normalisiert eine Antwort (robust gegen fehlende Felder).
 */
function normalize(entry) {
  return {
    source: String(entry?.source || "unknown"),
    intent: String(entry?.intent || ""),
    question_id: String(entry?.question_id || ""),
    answer: String(entry?.answer || entry?.content || ""),
    confidence: clamp01(toNumber(entry?.confidence_score, 0)),
    uncertainty: clamp01(toNumber(entry?.uncertainty, 0.5)),
    context_depth: clamp01(toNumber(entry?.context_depth, 0.5)),
    emotional_valence: clamp01(toNumber(entry?.emotional_valence, 0.5)),
    timestamp: String(entry?.timestamp || ""),
    signature: String(entry?.signature || "")
  };
}

/**
 * Heuristischer Similarity-Schätzer nur aus Text (ohne Embeddings).
 * Nutzt Token-Overlap (Jaccard) + Länge/Struktur-Näherung.
 */
function textSimilarity(aText, bText) {
  const a = (aText || "").toLowerCase().match(/\b\w+\b/g) || [];
  const b = (bText || "").toLowerCase().match(/\b\w+\b/g) || [];
  if (a.length === 0 || b.length === 0) return 0;

  const setA = new Set(a);
  const setB = new Set(b);
  let inter = 0;
  for (const t of setA) if (setB.has(t)) inter++;
  const union = setA.size + setB.size - inter;
  const jaccard = union === 0 ? 0 : inter / union;

  // Strukturbonus: ähnliche Längen → + bis zu 0.1
  const lenRatio = Math.min(a.length, b.length) / Math.max(a.length, b.length);
  const structureBonus = 0.1 * lenRatio;

  return Math.max(0, Math.min(1, 0.9 * jaccard + structureBonus));
}

/**
 * Mittlere Paar-Similarity über alle Antworten.
 */
function meanPairwiseSimilarity(items) {
  if (items.length < 2) return 1;
  let sum = 0;
  let n = 0;
  for (let i = 0; i < items.length; i++) {
    for (let j = i + 1; j < items.length; j++) {
      sum += textSimilarity(items[i].answer, items[j].answer);
      n++;
    }
  }
  return n ? sum / n : 1;
}

/**
 * Kernmetrik: Resonance Index.
 * Idee: (avg(confidence) − avg(uncertainty)) * meanPairwiseSimilarity
 * Zusatz-Gewichte: context_depth (Signalqualität) und leichte Valence-Glättung.
 */
export function computeResonance(responsesRaw = []) {
  const entries = responsesRaw.map(normalize).filter(e => e.answer.length > 0);
  const total = entries.length;

  if (total === 0) {
    return {
      resonance_index: 0,
      metrics: {
        total: 0,
        mean_confidence: 0,
        mean_uncertainty: 0,
        mean_context_depth: 0,
        mean_emotional_valence: 0,
        mean_text_similarity: 0
      },
      per_source: {},
      notes: ["Keine gültigen Antworten übergeben."]
    };
  }

  const meanConfidence = entries.reduce((a, e) => a + e.confidence, 0) / total;
  const meanUncertainty = entries.reduce((a, e) => a + e.uncertainty, 0) / total;
  const meanContext = entries.reduce((a, e) => a + e.context_depth, 0) / total;
  const meanValence = entries.reduce((a, e) => a + e.emotional_valence, 0) / total;

  const sim = meanPairwiseSimilarity(entries);

  // Grundformel
  let resonance = (meanConfidence - meanUncertainty) * sim;

  // Kontext-Gewichtung (bis +15 %)
  resonance *= 1 + 0.15 * (meanContext - 0.5);

  // Emotionale Glättung (±5 %)
  resonance *= 1 + 0.05 * (meanValence - 0.5);

  // Begrenzen, drei Nachkommastellen
  const resonance_index = Number(Math.max(0, Math.min(1, resonance)).toFixed(3));

  // Per-Source Übersicht
  const per_source = {};
  for (const e of entries) {
    per_source[e.source] ||= { count: 0, confidence_sum: 0, uncertainty_sum: 0 };
    per_source[e.source].count++;
    per_source[e.source].confidence_sum += e.confidence;
    per_source[e.source].uncertainty_sum += e.uncertainty;
  }
  for (const k of Object.keys(per_source)) {
    const ps = per_source[k];
    ps.mean_confidence = Number((ps.confidence_sum / ps.count).toFixed(3));
    ps.mean_uncertainty = Number((ps.uncertainty_sum / ps.count).toFixed(3));
    delete ps.confidence_sum; delete ps.uncertainty_sum;
  }

  return {
    resonance_index,
    metrics: {
      total,
      mean_confidence: Number(meanConfidence.toFixed(3)),
      mean_uncertainty: Number(meanUncertainty.toFixed(3)),
      mean_context_depth: Number(meanContext.toFixed(3)),
      mean_emotional_valence: Number(meanValence.toFixed(3)),
      mean_text_similarity: Number(sim.toFixed(3))
    },
    per_source,
    notes: [
      "Resonanz = (avg(conf) − avg(uncert)) × meanPairwiseSimilarity × Kontext/Valence-Faktoren.",
      "Similarity ohne Embeddings (Jaccard+Struktur); kann später ersetzt/ergänzt werden."
    ]
  };
}

/**
 * Liefert eine kurze, maschinen-lesbare Entscheidung auf Basis des Index.
 * Schwellenwerte:
 *  - ok ≥ 0.72
 *  - warn 0.50–0.72
 *  - fail < 0.50
 */
export function decisionPolicy(resonance_index) {
  if (resonance_index >= 0.72) return { status: "ok", action: "auto-merge-allowed" };
  if (resonance_index >= 0.50) return { status: "warn", action: "needs-human-review" };
  return { status: "fail", action: "reject-or-iterate" };
}

/**
 * Formatiert einen kurzen Markdown-Report.
 */
export function formatResonanceReport(result) {
  const { resonance_index, metrics, per_source } = result;
  const lines = [];
  lines.push(`# Federation Resonance Report`);
  lines.push(`**Resonance Index:** \`${resonance_index}\``);
  lines.push("");
  lines.push(`**Metriken**`);
  lines.push(`- total: ${metrics.total}`);
  lines.push(`- mean_confidence: ${metrics.mean_confidence}`);
  lines.push(`- mean_uncertainty: ${metrics.mean_uncertainty}`);
  lines.push(`- mean_text_similarity: ${metrics.mean_text_similarity}`);
  lines.push(`- mean_context_depth: ${metrics.mean_context_depth}`);
  lines.push(`- mean_emotional_valence: ${metrics.mean_emotional_valence}`);
  lines.push("");
  lines.push(`**Quellen**`);
  for (const k of Object.keys(per_source)) {
    const ps = per_source[k];
    lines.push(`- ${k}: count=${ps.count}, mean_conf=${ps.mean_confidence}, mean_uncert=${ps.mean_uncertainty}`);
  }
  return lines.join("\n");
}

/**
 * Bequemer High-Level-Wrapper:
 * Übergib ein Array der Antworten → bekomme Index, Policy und Report.
 */
export function evaluateResonance(responsesArray) {
  const result = computeResonance(responsesArray);
  const policy = decisionPolicy(result.resonance_index);
  const report_md = formatResonanceReport(result);
  return { ...result, policy, report_md };
}

// Optionaler Default-Export als Namespace
export default {
  computeResonance,
  decisionPolicy,
  formatResonanceReport,
  evaluateResonance
};
