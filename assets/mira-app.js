// assets/mira-app.js
// Zentrale Steuerung für:
// - Zeitstempel
// - Status / Selbstbild / Lernen
// - Bild / Video / Audio (Play/Pause)

// Kleine Hilfsfunktion für JSON-Requests
async function fetchJson(path) {
  try {
    const res = await fetch(path + "?v=" + Date.now());
    if (!res.ok) throw new Error("HTTP " + res.status);
    return await res.json();
  } catch (e) {
    return null;
  }
}

function select(id) {
  return document.getElementById(id);
}

const liveTsEl = select("live-timestamp");

const portraitFrame = select("portrait-frame");
const portraitVideo = select("portrait-video");
const portraitImg = select("portrait-img");
const portraitPlaceholder = select("portrait-placeholder");
const imageMeta = select("image-meta");
const imageStatus = select("image-status");

const audioEl = select("voice");
const btnPlay = select("btn-play");
const btnPause = select("btn-pause");
const audioStatus = select("audio-status");

const quoteText = select("quote-text");
const baseTone = select("base-tone");
const quoteUpdated = select("quote-updated");
const toneTag = select("tone-tag");
const toneTagLabel = select("tone-tag-label");

const selfimageSummary = select("selfimage-summary");
const learningSummary = select("learning-summary");
const versionPill = select("version-pill");

let videoAvailable = false;

// Zeitstempel
function updateLiveTimestamp() {
  const now = new Date();
  const iso = now.toISOString().replace(/\.\d+Z$/, "Z");
  if (liveTsEl) liveTsEl.textContent = iso;
}

// Theme / Farben je nach Grundton
function applyToneTheme(toneRaw) {
  if (!toneRaw) return;
  const tone = String(toneRaw).toLowerCase();

  let accent = "#3ce081";
  let accentSoft = "rgba(60, 224, 129, 0.26)";
  let bgMain = "radial-gradient(circle at top, #151f3b 0%, #050813 55%, #02030a 100%)";
  let cardBg = "linear-gradient(145deg, rgba(255,255,255,0.07), rgba(7,10,24,0.95))";
  let label = toneRaw;

  if (tone.includes("ruhig") || tone.includes("klar") || tone.includes("still")) {
    accent = "#3fb7ff";
    accentSoft = "rgba(63, 183, 255, 0.26)";
    bgMain = "radial-gradient(circle at top, #0c1830 0%, #020615 55%, #02030a 100%)";
    label = toneRaw + " · klarer Himmel";
  } else if (tone.includes("warm") || tone.includes("zugewandt") || tone.includes("sanft")) {
    accent = "#ffb74d";
    accentSoft = "rgba(255, 183, 77, 0.26)";
    bgMain = "radial-gradient(circle at top, #28140a 0%, #12080a 55%, #030108 100%)";
    label = toneRaw + " · goldene Stunde";
  } else if (tone.includes("intensiv") || tone.includes("lebendig") || tone.includes("kraftvoll")) {
    accent = "#ff6fa8";
    accentSoft = "rgba(255, 111, 168, 0.28)";
    bgMain = "radial-gradient(circle at top, #2b0620 0%, #100411 55%, #05000a 100%)";
    label = toneRaw + " · hohe Energie";
  } else if (tone.includes("melanchol")) {
    accent = "#8e9cff";
    accentSoft = "rgba(142,156,255,0.3)";
    bgMain = "radial-gradient(circle at top, #0f1028 0%, #060616 55%, #020107 100%)";
    label = toneRaw + " · leise Tiefe";
  }

  document.documentElement.style.setProperty("--accent", accent);
  document.documentElement.style.setProperty("--accent-soft", accentSoft);
  document.documentElement.style.setProperty("--bg-main", bgMain);
  document.documentElement.style.setProperty("--card-bg", cardBg);

  if (toneTag && toneTagLabel) {
    toneTag.style.display = "inline-flex";
    toneTagLabel.textContent = label;
  }
}

// Status / Tagesimpuls laden
async function loadStatus() {
  const data = await fetchJson("data/self/status.json");
  if (!data || typeof data !== "object") {
    if (quoteText) quoteText.textContent = "Noch kein Tagesimpuls eingetragen.";
    if (baseTone) baseTone.textContent = "unbestimmt";
    if (quoteUpdated) quoteUpdated.textContent = "—";
    return;
  }

  if (quoteText) {
    quoteText.textContent =
      data.daily_quote || "Noch kein Tagesimpuls eingetragen.";
  }
  const tone = data.base_tone || "unbestimmt";
  if (baseTone) baseTone.textContent = tone;
  if (quoteUpdated) quoteUpdated.textContent = data.updated_at || "—";
  applyToneTheme(tone);
}

// Selbstbild / Entwicklung laden
async function loadSelfImage() {
  const data = await fetchJson("data/self/portrait_state.json");
  if (!data || typeof data !== "object") {
    if (selfimageSummary) {
      selfimageSummary.textContent = "Noch kein explizites Selbstbild hinterlegt.";
    }
    return;
  }

  const summary =
    data.summary ||
    data.description ||
    data.current_self_image ||
    "";
  const evo =
    data.evolution_note ||
    data.trajectory ||
    data.development_path?.long_term ||
    "";

  let text = "";
  if (summary) text += summary;
  if (evo) text += (text ? " " : "") + evo;

  if (!text) {
    text =
      "Daten zum Selbstbild sind vorhanden, aber ohne Kurzbeschreibung.";
  }

  if (selfimageSummary) selfimageSummary.textContent = text;

  const version =
    data.version ||
    data.portrait_version ||
    "";
  if (version && versionPill) {
    versionPill.style.display = "inline-block";
    versionPill.textContent = "Selbstbild-Version: " + version;
  }
}

// Lernstatus laden
async function loadLearning() {
  const data = await fetchJson("data/self/learning.json");
  if (!data || typeof data !== "object") {
    if (learningSummary) {
      learningSummary.textContent = "Noch kein Lernstatus hinterlegt.";
    }
    return;
  }

  const next =
    data.next_focus ||
    data.next_step ||
    data.note ||
    data.trajectory ||
    "";
  if (next && learningSummary) {
    learningSummary.textContent = "Aktueller Lernfokus: " + next;
  } else if (learningSummary) {
    learningSummary.textContent =
      "Lernstatus vorhanden, aber ohne klaren Fokus-Text.";
  }
}

// Bild-Fallback initialisieren
function initImageFallback() {
  if (!portraitImg || !portraitPlaceholder || !imageMeta || !imageStatus) return;

  portraitVideo.style.display = "none";

  const src = "data/self/latest_image.png?v=" + Date.now();
  imageStatus.textContent = "Status: lade Portrait-Bild …";

  portraitImg.onload = function () {
    portraitPlaceholder.style.display = "none";
    portraitImg.style.display = "block";
    imageMeta.textContent = "Medium: Bild (data/self/latest_image.png)";
    imageStatus.textContent = "Status: Bild geladen";
  };

  portraitImg.onerror = function () {
    portraitImg.style.display = "none";
    portraitPlaceholder.style.display = "flex";
    portraitPlaceholder.textContent = "Kein aktuelles Bild gefunden.";
    imageMeta.textContent = "Medium: —";
    imageStatus.textContent = "Status: kein Bild vorhanden";
  };

  portraitImg.src = src;
}

// Medien initialisieren: erst Video versuchen, sonst Bild
function initMedia() {
  if (!portraitVideo || !portraitImg || !portraitPlaceholder) return;

  // Versuch: Video vorbereiten
  portraitVideo.src = "data/self/latest_video.mp4?v=" + Date.now();

  portraitVideo.addEventListener("loadeddata", function () {
    videoAvailable = true;
    portraitPlaceholder.style.display = "none";
    portraitImg.style.display = "none";
    portraitVideo.style.display = "block";
    if (imageMeta) {
      imageMeta.textContent = "Medium: Video (data/self/latest_video.mp4)";
    }
    if (imageStatus) {
      imageStatus.textContent = "Status: Video erkannt – Tippe ▶ zum Starten.";
    }
  });

  portraitVideo.addEventListener("error", function () {
    // Video ging nicht → Bild-Fallback
    initImageFallback();
  });

  // Falls gar nichts passiert, nach kurzer Zeit auch auf Bild-Fallback gehen
  setTimeout(function () {
    if (!videoAvailable) {
      initImageFallback();
    }
  }, 2000);
}

// Audio vorbereiten
function initAudio() {
  if (!audioEl || !audioStatus) return;

  audioEl.addEventListener("canplaythrough", function () {
    if (!videoAvailable) {
      audioStatus.textContent = "Bereit – Tippe ▶, damit Mira spricht.";
    }
  });
}

function setSpeaking(active, label) {
  if (!portraitFrame || !audioStatus) return;
  if (active) {
    portraitFrame.classList.remove("m-state-idle");
    portraitFrame.classList.add("m-state-speaking");
    audioStatus.textContent = label + " spielt.";
  } else {
    portraitFrame.classList.remove("m-state-speaking");
    portraitFrame.classList.add("m-state-idle");
  }
}

// Buttons verbinden
function initControls() {
  if (!btnPlay || !btnPause) return;

  btnPlay.addEventListener("click", async function () {
    // 1) Wenn Video vorhanden → zuerst Video
    if (videoAvailable && portraitVideo) {
      try {
        await portraitVideo.play();
        setSpeaking(true, "Video");
        return;
      } catch (e) {
        // Wenn Video nicht startet → weiter zu Audio
      }
    }

    // 2) Fallback: Audio
    if (audioEl) {
      try {
        await audioEl.play();
        setSpeaking(true, "Audio");
      } catch (e2) {
        audioStatus.textContent =
          "Konnte nicht starten – bitte erneut ▶ tippen oder Browser-Einstellungen prüfen.";
      }
    }
  });

  btnPause.addEventListener("click", function () {
    if (portraitVideo) portraitVideo.pause();
    if (audioEl) audioEl.pause();
    setSpeaking(false, "Wiedergabe");
    if (audioStatus) audioStatus.textContent = "Pausiert.";
  });

  if (portraitVideo) {
    portraitVideo.addEventListener("ended", function () {
      setSpeaking(false, "Video");
      if (audioStatus) {
        audioStatus.textContent =
          "Video beendet – du kannst jederzeit erneut ▶ drücken.";
      }
    });
  }

  if (audioEl) {
    audioEl.addEventListener("ended", function () {
      setSpeaking(false, "Audio");
      if (audioStatus) {
        audioStatus.textContent =
          "Audio beendet – du kannst jederzeit erneut ▶ drücken.";
      }
    });
  }
}

// Hauptstart
function initApp() {
  updateLiveTimestamp();

  initMedia();
  initAudio();
  initControls();

  loadStatus();
  loadSelfImage();
  loadLearning();
}

document.addEventListener("DOMContentLoaded", initApp);
