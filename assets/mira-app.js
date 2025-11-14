// -------------------------------------------------------------
// MIRA APP – zentraler Kern
// Nutzt:
//   - modules/assetModule.js für Video/Bild-Fallback
//   - internes Audio-Handling (WAV → MP3)
//   - JSON-Loader für Status, Selbstbild, Lernen
// -------------------------------------------------------------

import { loadMedia as loadHeroMedia } from "./modules/assetModule.js";

// ---- AUDIO LOADER ------------------------------------------------

export async function loadAudio() {
  const audio = document.getElementById("voice");
  const statusEl = document.getElementById("audio-status");
  if (!audio) return;

  // WAV bevorzugen
  let chosen = null;

  const wavOK = await fetch("audio/latest.wav", { method: "HEAD" })
    .then(r => r.ok)
    .catch(() => false);

  if (wavOK) {
    audio.src = "audio/latest.wav?v=" + Date.now();
    chosen = "wav";
  } else {
    const mp3OK = await fetch("audio/latest.mp3", { method: "HEAD" })
      .then(r => r.ok)
      .catch(() => false);
    if (mp3OK) {
      audio.src = "audio/latest.mp3?v=" + Date.now();
      chosen = "mp3";
    }
  }

  if (!chosen) {
    audio.removeAttribute("src");
    if (statusEl) {
      statusEl.textContent = "Kein Audio gefunden.";
    }
    return "none";
  }

  if (statusEl) {
    statusEl.textContent = "Bereit – Tippe ▶, damit Mira spricht.";
  }
  return chosen;
}

// ---- JSON HELFER -------------------------------------------------

async function safeLoadJson(path) {
  try {
    const res = await fetch(path + "?v=" + Date.now());
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ---- JSON GESAMTLADELOGIK ----------------------------------------

export async function loadAllJson() {
  const quoteEl = document.getElementById("quote");
  const selfBox = document.getElementById("selfbox");
  const learningBox = document.getElementById("learningbox");

  const [status, self, learning] = await Promise.all([
    safeLoadJson("data/self/status.json"),
    safeLoadJson("data/self/self-describe.json"),
    safeLoadJson("data/self/learning.json")
  ]);

  // Tagesimpuls
  if (quoteEl) {
    if (status && status.daily_quote) {
      quoteEl.textContent = status.daily_quote;
    } else {
      quoteEl.textContent = "Noch kein Tagesimpuls eingetragen.";
    }
  }

  // Selbstbild
  if (selfBox) {
    if (self && typeof self === "object") {
      const phys = self.physical?.description || "—";
      const voice = self.voice?.profile || "—";
      const affect = self.affect?.narrative || "—";

      selfBox.innerHTML =
        `<b>Körper:</b> ${phys}<br>` +
        `<b>Stimme:</b> ${voice}<br>` +
        `<b>Affekt:</b> ${affect}`;
    } else {
      selfBox.textContent = "Noch kein explizites Selbstbild hinterlegt.";
    }
  }

  // Lernen
  if (learningBox) {
    if (learning && learning.next_focus) {
      learningBox.textContent = "Aktueller Lernfokus: " + learning.next_focus;
    } else if (learning) {
      learningBox.textContent =
        "Lernstatus vorhanden, aber ohne klaren Fokus-Text.";
    } else {
      learningBox.textContent = "Noch kein Lernstatus hinterlegt.";
    }
  }
}

// ---- INIT --------------------------------------------------------

export async function initApp() {
  // Medien (Video/Bild)
  await loadHeroMedia("mediaContainer");

  // Audio
  await loadAudio();

  // JSON-Zustände
  await loadAllJson();

  console.log("Mira-App initialisiert.");
}
