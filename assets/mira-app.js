// assets/mira-app.js
// Zentrale Steuerung für:
// - Zeitstempel / Live-Anzeige
// - Porträt (Video → Bild → Platzhalter)
// - Audio (Play/Pause)
// - Tagesimpuls / Selbstbild / Lernen

// Kleine Hilfsfunktion für JSON-Requests
async function fetchJson(path) {
  try {
    const res = await fetch(path + "?v=" + Date.now());
    if (!res.ok) throw new Error("HTTP " + res.status);
    return await res.json();
  } catch (e) {
    console.warn("fetchJson failed for", path, e);
    return null;
  }
}

function $(id) {
  return document.getElementById(id);
}

// --- Referenzen auf DOM-Elemente ---

const liveTsEl = $("live-timestamp");

const portraitFrame = $("portrait-frame");
const portraitVideo = $("portrait-video");
const portraitImg = $("portrait-img");
const portraitPlaceholder = $("portrait-placeholder");
const imageMeta = $("image-meta");
const imageStatus = $("image-status");

const audioEl = $("voice");
const btnPlay = $("btn-play");
const btnPause = $("btn-pause");
const audioStatus = $("audio-status");

const quoteText = $("quote-text");
const baseTone = $("base-tone");
const quoteUpdated = $("quote-updated");
const toneTag = $("tone-tag");
const toneTagLabel = $("tone-tag-label");

const selfimageSummary = $("selfimage-summary");
const learningSummary = $("learning-summary");
const versionPill = $("version-pill");

let currentMediaMode = "image"; // "video" oder "image"
let audioIsReady = false;

// --- Live-Timestamp ---

function updateLiveTimestamp() {
  if (!liveTsEl) return;
  const now = new Date();
  const iso = now.toISOString().replace(/\.\d+Z$/, "Z");
  liveTsEl.textContent = iso;
}

// --- Theme / Farben je nach Grundton ---

function applyToneTheme(toneRaw) {
  if (!toneRaw) return;
  const tone = String(toneRaw).toLowerCase();

  let accent = "#3ce081";
  let accentSoft = "rgba(60, 224, 129, 0.26)";
  let bgMain =
    "radial-gradient(circle at top, #151f3b 0%, #050813 55%, #02030a 100%)";
  let cardBg =
    "linear-gradient(145deg, rgba(255,255,255,0.07), rgba(7,10,24,0.95))";
  let label = toneRaw;

  if (
    tone.includes("ruhig") ||
    tone.includes("klar") ||
    tone.includes("still")
  ) {
    accent = "#3fb7ff";
    accentSoft = "rgba(63, 183, 255, 0.26)";
    bgMain =
      "radial-gradient(circle at top, #0c1830 0%, #020615 55%, #02030a 100%)";
    label = toneRaw + " · klarer Himmel";
  } else if (
    tone.includes("warm") ||
    tone.includes("zugewandt") ||
    tone.includes("sanft")
  ) {
    accent = "#ffb74d";
    accentSoft = "rgba(255, 183, 77, 0.26)";
    bgMain =
      "radial-gradient(circle at top, #28140a 0%, #12080a 55%, #030108 100%)";
    label = toneRaw + " · goldene Stunde";
  } else if (
    tone.includes("intensiv") ||
    tone.includes("lebendig") ||
    tone.includes("kraftvoll")
  ) {
    accent = "#ff6fa8";
    accentSoft = "rgba(255, 111, 168, 0.28)";
    bgMain =
      "radial-gradient(circle at top, #2b0620 0%, #100411 55%, #05000a 100%)";
    label = toneRaw + " · hohe Energie";
  } else if (tone.includes("melanchol")) {
    accent = "#8e9cff";
    accentSoft = "rgba(142, 156, 255, 0.3)";
    bgMain =
      "radial-gradient(circle at top, #0f1028 0%, #060616 55%, #020107 100%)";
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

// --- Porträt: Video → Bild → Platzhalter ---

function showPlaceholder(message) {
  if (portraitVideo) {
    portraitVideo.style.display = "none";
    portraitVideo.removeAttribute("src");
  }
  if (portraitImg) {
    portraitImg.style.display = "none";
    portraitImg.removeAttribute("src");
  }
  if (portraitPlaceholder) {
    portraitPlaceholder.style.display = "flex";
    portraitPlaceholder.textContent =
      message || "Noch kein Bild oder Video verfügbar.";
  }
  currentMediaMode = "none";
  if (imageMeta) imageMeta.textContent = "Medium: —";
  if (imageStatus) imageStatus.textContent = "Status: Wartet auf Medien …";
}

function showImage(path) {
  if (!portraitImg) return;

  if (portraitVideo) {
    portraitVideo.pause();
    portraitVideo.style.display = "none";
    portraitVideo.removeAttribute("src");
  }

  portraitPlaceholder.style.display = "none";
  portraitImg.style.display = "block";
  portraitImg.src = path + "?ts=" + Date.now();

  currentMediaMode = "image";
  if (imageMeta) imageMeta.textContent = "Medium: Bild · " + path;
  if (imageStatus) imageStatus.textContent = "Status: Bild geladen.";
}

function tryLoadImageFallback() {
  showImage("data/self/latest_image.png");

  if (portraitImg) {
    portraitImg.onerror = function () {
      showPlaceholder("Kein aktuelles Porträt vorhanden.");
    };
  }
}

function initPortraitMedia() {
  if (!portraitFrame || !portraitVideo || !portraitImg || !portraitPlaceholder) {
    // Falls das Layout anders ist, nichts tun.
    return;
  }

  // Erst mal Platzhalter zeigen
  portraitPlaceholder.style.display = "flex";
  portraitImg.style.display = "none";
  portraitVideo.style.display = "none";

  if (imageStatus)
    imageStatus.textContent = "Status: Versuche Video zu laden …";

  const videoPath = "data/self/latest_video.mp4";

  // Event-Handler nur einmal konfigurieren
  portraitVideo.preload = "metadata";
  portraitVideo.playsInline = true;
  portraitVideo.muted = true; // bleibt optisch stumm; Audio kommt aus <audio>

  portraitVideo.onloadeddata = function () {
    // Video erfolgreich
    portraitPlaceholder.style.display = "none";
    portraitImg.style.display = "none";
    portraitVideo.style.display = "block";

    currentMediaMode = "video";
    if (imageMeta) imageMeta.textContent = "Medium: Video · " + videoPath;
    if (imageStatus) imageStatus.textContent = "Status: Video geladen.";
  };

  portraitVideo.onerror = function () {
    // Wenn Video nicht geht → Bild-Fallback
    tryLoadImageFallback();
  };

  // Soft-Fallback bei "stalled": nach 15 s auf Bild umschalten
  portraitVideo.onstalled = function () {
    setTimeout(function () {
      if (portraitVideo.readyState < 2 && currentMediaMode !== "image") {
        tryLoadImageFallback();
      }
    }, 15000);
  };

  // Video-URL setzen (mit Cache-Buster)
  portraitVideo.src = videoPath + "?ts=" + Date.now();
}

// --- Audio: WAV/MP3 mit Play/Pause ---

function initAudio() {
  if (!audioEl) return;

  // Formatwahl per canPlayType
  try {
    const wavOk =
      audioEl.canPlayType("audio/wav") === "probably" ||
      audioEl.canPlayType("audio/wav") === "maybe";
    const mp3Ok =
      audioEl.canPlayType("audio/mpeg") === "probably" ||
      audioEl.canPlayType("audio/mpeg") === "maybe";

    if (wavOk) {
      audioEl.src = "audio/latest.wav?ts=" + Date.now();
    } else if (mp3Ok) {
      audioEl.src = "audio/latest.mp3?ts=" + Date.now();
    } else {
      if (audioStatus)
        audioStatus.textContent =
          "Kein unterstütztes Audioformat im Browser verfügbar.";
      return;
    }

    audioIsReady = true;
    if (audioStatus)
      audioStatus.textContent =
        "Bereit – tippe auf ▶, um Mira zu hören.";
  } catch (e) {
    console.warn("Audio init failed", e);
    if (audioStatus)
      audioStatus.textContent = "Fehler beim Initialisieren des Audios.";
  }

  // Buttons
  if (btnPlay) {
    btnPlay.onclick = function () {
      if (!audioIsReady) return;
      audioEl
        .play()
        .then(function () {
          if (audioStatus) audioStatus.textContent = "Spielt.";
          if (portraitFrame) {
            portraitFrame.classList.remove("idle");
            portraitFrame.classList.add("speaking");
          }
        })
        .catch(function (err) {
          console.warn("Audio play blocked", err);
          if (audioStatus)
            audioStatus.textContent =
              "Wiedergabe blockiert – bitte noch einmal ▶ tippen.";
        });
    };
  }

  if (btnPause) {
    btnPause.onclick = function () {
      audioEl.pause();
      if (audioStatus) audioStatus.textContent = "Pausiert.";
      if (portraitFrame) {
        portraitFrame.classList.remove("speaking");
        portraitFrame.classList.add("idle");
      }
    };
  }

  // Wenn Audio von selbst zu Ende ist
  audioEl.onended = function () {
    if (audioStatus) audioStatus.textContent = "Beendet.";
    if (portraitFrame) {
      portraitFrame.classList.remove("speaking");
      portraitFrame.classList.add("idle");
    }
  };
}

// --- Tagesimpuls / Status laden ---

async function loadStatus() {
  if (!quoteText || !baseTone) return;

  const data = await fetchJson("data/self/status.json");
  if (!data || typeof data !== "object") {
    quoteText.textContent = "Noch kein Tagesimpuls eingetragen.";
    baseTone.textContent = "unbestimmt";
    if (quoteUpdated) quoteUpdated.textContent = "—";
    if (imageStatus && currentMediaMode === "none") {
      imageStatus.textContent = "Status: Noch keine Statusdaten.";
    }
    return;
  }

  quoteText.textContent =
    data.daily_quote ||
    data.daily_input ||
    "Noch kein Tagesimpuls eingetragen.";
  baseTone.textContent = data.base_tone || "unbestimmt";
  if (quoteUpdated) quoteUpdated.textContent = data.updated_at || "—";

  applyToneTheme(data.base_tone || "");
}

// --- Selbstbild & Lernen laden ---

async function loadSelfview() {
  if (selfimageSummary) {
    const portraitState = await fetchJson("data/self/portrait_state.json");
    if (portraitState && typeof portraitState === "object") {
      const ver = portraitState.version || portraitState.id || "—";
      const desc =
        portraitState.description ||
        portraitState.summary ||
        "Aktuelles Porträt ist eingetragen.";
      selfimageSummary.innerHTML =
        "<b>Porträtstatus:</b> " + desc + "<br><span class='mono'>Version: " + ver + "</span>";
      if (versionPill) {
        versionPill.style.display = "inline-block";
        versionPill.textContent = "Portrait v" + ver;
      }
    } else {
      selfimageSummary.textContent =
        "Noch kein detaillierter Porträtstatus eingetragen.";
    }
  }

  if (learningSummary) {
    const learning = await fetchJson("data/self/learning.json");
    if (learning && typeof learning === "object") {
      const focus =
        learning.focus ||
        learning.current ||
        "Lernfokus noch nicht festgelegt.";
      const note = learning.note || learning.comment || "";
      learningSummary.innerHTML =
        "<b>Lernfokus:</b> " +
        focus +
        (note ? "<br><span class='mono'>" + note + "</span>" : "");
    } else {
      learningSummary.textContent =
        "Noch keine expliziten Lernziele eingetragen.";
    }
  }
}

// --- Initialisierung & Polling ---

async function initMira() {
  updateLiveTimestamp();
  setInterval(updateLiveTimestamp, 30_000);

  initPortraitMedia();
  initAudio();
  loadStatus();
  loadSelfview();

  // optionale sanfte Aktualisierung alle 60 Sekunden
  setInterval(function () {
    loadStatus();
    loadSelfview();
  }, 60_000);
}

// Start
document.addEventListener("DOMContentLoaded", function () {
  initMira().catch(function (e) {
    console.error("Init failed:", e);
  });
});
