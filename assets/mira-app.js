// assets/mira-app.js
// ZENTRALE STEUERUNG: lädt alle Module (Media, Audio, JSON)
// und initialisiert Mira vollständig.

import { initMedia } from './modules/assets.js';
import { initAudio } from './modules/audio.js';
import { initJson } from './modules/json.js';

// Warten, bis der DOM fertig ist
document.addEventListener("DOMContentLoaded", function () {
  console.log("[mira-app] Starte Initialisierung …");

  // 1) Bild/Video
  try {
    initMedia();
    console.log("[mira-app] Media-Modul geladen.");
  } catch (err) {
    console.error("[mira-app] Fehler im Media-Modul:", err);
  }

  // 2) Audio
  try {
    initAudio();
    console.log("[mira-app] Audio-Modul geladen.");
  } catch (err) {
    console.error("[mira-app] Fehler im Audio-Modul:", err);
  }

  // 3) JSON
  try {
    initJson();
    console.log("[mira-app] JSON-Modul geladen.");
  } catch (err) {
    console.error("[mira-app] Fehler im JSON-Modul:", err);
  }

  console.log("[mira-app] Initialisierung abgeschlossen.");
});
