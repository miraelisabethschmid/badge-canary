// assets/mira-app.js
// Zentrale Orchestrierung: Medien, Audio, JSON & Live-Timestamp

import { initMedia } from "./modules/assets.js";
import { initAudio } from "./modules/audio.js";
import { initJson } from "./modules/json.js";

function updateLiveTimestamp() {
  const el = document.getElementById("live-timestamp");
  if (!el) return;
  const now = new Date();
  const iso = now.toISOString().replace(/\.\d+Z$/, "Z");
  el.textContent = iso;
}

document.addEventListener("DOMContentLoaded", () => {
  // Live-Zeitstempel direkt und dann regelmäßig aktualisieren
  updateLiveTimestamp();
  setInterval(updateLiveTimestamp, 30000); // alle 30 Sekunden

  // Medien (Video/Bild/Platzhalter)
  try {
    initMedia();
  } catch (e) {
    console.error("initMedia() fehlgeschlagen:", e);
  }

  // Audio / Buttons
  try {
    initAudio();
  } catch (e) {
    console.error("initAudio() fehlgeschlagen:", e);
  }

  // JSON: Tagesimpuls, Selbstbild, Lernen
  try {
    initJson();
  } catch (e) {
    console.error("initJson() fehlgeschlagen:", e);
  }
});
