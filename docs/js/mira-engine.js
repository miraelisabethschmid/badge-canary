// ---------------------------------------------------------
// MIRA ENGINE — Grundsystem zur Verarbeitung von:
// - Emotionen (emotion_state.json)
// - Affekten (affect_model.yml via JSON Proxy)
// - Selbstbild (portrait_state.json)
// - Identität (meta_state.json)
// - Lernen (learning.json)
// - Tagesstatus (status.json)
// ---------------------------------------------------------
// Version 1.0 — Stabiler Basiskern (keine Animation aktiv)
// ---------------------------------------------------------

async function loadJSON(path) {
  try {
    const res = await fetch(path + '?t=' + Date.now(), {
      method: 'GET',
      cache: 'no-store'
    });
    if (!res.ok) throw new Error('Fehler beim Laden: ' + path);
    return await res.json();
  } catch (e) {
    console.warn('⚠️ ' + e.message);
    return null;
  }
}

// ---------------------------------------------------------
// Hauptladefunktion
// ---------------------------------------------------------

export async function Mira_LoadCore() {
  const core = {};

  core.status = await loadJSON('/badge-canary/data/self/status.json');
  core.emotion = await loadJSON('/badge-canary/data/self/emotion_state.json');
  core.meta = await loadJSON('/badge-canary/data/self/meta_state.json');
  core.learning = await loadJSON('/badge-canary/data/self/learning.json');
  core.portrait = await loadJSON('/badge-canary/data/self/portrait_state.json');

  console.log('%cMira Core geladen:', 'color:#8ef;', core);
  return core;
}

// ---------------------------------------------------------
// Analysefunktion — entscheidet, wie Mira sich fühlen soll
// (Noch keine sichtbare Animation, nur Logik.)
// ---------------------------------------------------------

export function Mira_CurrentExpression(core) {
  if (!core || !core.emotion) return null;

  const e = core.emotion.current_emotion;
  const m = core.emotion.micro_expression;

  return {
    mood: e.label,
    intensity: e.intensity,
    warmth: e.warmth,
    energy: e.energy,
    mouth_tension: m.mouth_tension,
    eye_softness: m.eye_softness,
    brow_relaxation: m.brow_relaxation
  };
}

// ---------------------------------------------------------
// Vorbereitung für zukünftige Lippenbewegung
// ---------------------------------------------------------

export function Mira_MouthMovementFromAudio(volume) {
  // Volume 0.0–1.0 → Mundöffnungsgrad
  const scale = Math.min(1, Math.max(0, volume));
  return scale * 0.9;
}

// ---------------------------------------------------------
// Platzhalter für zukünftige Live-Mimik (noch deaktiviert)
// ---------------------------------------------------------

export function Mira_ApplyExpression(expr) {
  // Hier später DOM-Animationen und Bildwechsel.
  // Aktuell bewusst leer gelassen, um Stabilität zu sichern.
  console.log('%cExpression Update:', 'color:#fc8;', expr);
}

// ---------------------------------------------------------
// Gesamtsystem starten (kann direkt aus index.html aufgerufen werden)
// ---------------------------------------------------------

export async function Mira_Start() {
  const core = await Mira_LoadCore();
  const expr = Mira_CurrentExpression(core);
  Mira_ApplyExpression(expr);
  return core;
}

console.log('%cMira Engine bereit.', 'color:#9f9; font-weight:bold;');
