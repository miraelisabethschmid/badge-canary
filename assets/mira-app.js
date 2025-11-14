// assets/mira-app.js

const VIDEO_SRC = "data/self/latest_video.mp4";
const IMAGE_SRC = "data/self/latest_image.png";
const STATUS_JSON = "data/self/status.json";
const AUDIO_WAV = "audio/latest.wav";
const AUDIO_MP3 = "audio/latest.mp3";

function cacheBust(url) {
  const ts = Date.now();
  if (url.includes("?")) return `${url}&v=${ts}`;
  return `${url}?v=${ts}`;
}

function initMedia() {
  const video = document.getElementById("portrait-video");
  const img = document.getElementById("portrait-image");
  const placeholder = document.getElementById("portrait-placeholder");
  const statusLine = document.getElementById("media-status-line");

  if (!video || !img || !placeholder) return;

  // Setze Quellen mit Cache-Busting
  video.src = cacheBust(VIDEO_SRC);
  img.src = cacheBust(IMAGE_SRC);

  let videoLoaded = false;

  video.addEventListener("loadeddata", () => {
    videoLoaded = true;
    video.style.display = "block";
    img.style.display = "none";
    placeholder.style.display = "none";

    if (statusLine) {
      statusLine.textContent =
        "Aktiv: Video (data/self/latest_video.mp4) · Bild verfügbar als Fallback";
    }
  });

  video.addEventListener("error", () => {
    // Video konnte nicht geladen werden → Bild versuchen
    video.style.display = "none";

    img.onload = () => {
      img.style.display = "block";
      placeholder.style.display = "none";
      if (statusLine) {
        statusLine.textContent =
          "Aktiv: Bild (data/self/latest_image.png) · Video nicht verfügbar";
      }
    };

    img.onerror = () => {
      img.style.display = "none";
      placeholder.style.display = "block";
      if (statusLine) {
        statusLine.textContent =
          "Weder Bild noch Video verfügbar. Bitte Assets prüfen.";
      }
    };

    // Bild neu setzen mit Cache-Bust
    img.src = cacheBust(IMAGE_SRC);
  });

  // Falls der Browser das Video nie lädt (z.B. sehr exotisch),
  // lassen wir das Bild als Default stehen. Kein Timer nötig.
}

function initAudio() {
  const audio = document.getElementById("mira-audio");
  const statusLine = document.getElementById("audio-status-line");
  if (!audio) return;

  // Wir setzen nur EINE Quelle, je nach Support
  const wavSupported =
    audio.canPlayType("audio/wav") === "probably" ||
    audio.canPlayType("audio/wav") === "maybe";

  const mp3Supported =
    audio.canPlayType("audio/mpeg") === "probably" ||
    audio.canPlayType("audio/mpeg") === "maybe";

  if (wavSupported) {
    audio.src = cacheBust(AUDIO_WAV);
    if (statusLine) {
      statusLine.textContent = "Audio: audio/latest.wav (primär, WAV-Unterstützung erkannt)";
    }
  } else if (mp3Supported) {
    audio.src = cacheBust(AUDIO_MP3);
    if (statusLine) {
      statusLine.textContent = "Audio: audio/latest.mp3 (Fallback, WAV nicht unterstützt)";
    }
  } else {
    audio.removeAttribute("src");
    if (statusLine) {
      statusLine.textContent =
        "Kein unterstütztes Audioformat gefunden. Bitte Browser oder Datei prüfen.";
    }
  }
}

async function initStatus() {
  const quoteElement = document.getElementById("quote-text");
  if (!quoteElement) return;

  try {
    const res = await fetch(cacheBust(STATUS_JSON), {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!res.ok) {
      quoteElement.textContent =
        "Noch kein Spruch des Tages hinterlegt (HTTP-Fehler: " + res.status + ").";
      return;
    }

    const data = await res.json();

    // Versuche verschiedene Feldnamen – je nachdem, wie das JSON aufgebaut ist
    const quote =
      data.daily_quote ||
      data.spruch_des_tages ||
      data.quote ||
      data.text ||
      data.message ||
      "";

    if (quote && typeof quote === "string") {
      quoteElement.textContent = quote;
    } else {
      quoteElement.textContent =
        "Noch kein Spruch des Tages im JSON gefunden.";
    }
  } catch (err) {
    console.error("Fehler beim Laden von status.json:", err);
    quoteElement.textContent =
      "Spruch des Tages konnte nicht geladen werden (Netzwerk- oder JSON-Fehler).";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initMedia();
  initAudio();
  initStatus();
});
