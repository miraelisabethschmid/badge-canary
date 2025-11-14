// -------------------------------------------------------------
// MIRA APP – zentraler Kern
// Lädt: Video → Bild → Platzhalter
// Lädt Audio: WAV → MP3
// Lädt JSON-Dateien (status, self, learning)
// Zukunft: Avatar + LipSync Hook
// -------------------------------------------------------------

// ---- MEDIA LOADER ------------------------------------------------

export async function loadMedia() {
  const mediaContainer = document.getElementById("mediaContainer");

  // 1) VIDEO versuchen
  const videoPath = "./data/self/latest_video.mp4";
  const video = document.createElement("video");
  video.src = videoPath + "?v=" + Date.now();
  video.autoplay = true;
  video.loop = true;
  video.muted = true;
  video.playsInline = true;

  const videoOK = await fetch(videoPath, { method: "HEAD" })
    .then(res => res.ok)
    .catch(() => false);

  if (videoOK) {
    mediaContainer.innerHTML = "";
    mediaContainer.appendChild(video);
    return "video";
  }

  // 2) BILD versuchen
  const imgPath = "./data/self/latest_image.png";
  const img = new Image();
  img.src = imgPath + "?v=" + Date.now();

  const imgOK = await fetch(imgPath, { method: "HEAD" })
    .then(res => res.ok)
    .catch(() => false);

  if (imgOK) {
    mediaContainer.innerHTML = "";
    mediaContainer.appendChild(img);
    return "image";
  }

  // 3) KEIN MEDIUM → Platzhalter
  mediaContainer.innerHTML = "<div style='padding:20px;text-align:center;'>Kein Medium verfügbar</div>";
  return "none";
}


// ---- AUDIO LOADER ----------------------------------------------

export async function loadAudio() {
  const audio = document.getElementById("voice");

  // WAV bevorzugen
  const wavOK = await fetch("./audio/latest.wav", { method: "HEAD" })
    .then(r => r.ok)
    .catch(() => false);

  if (wavOK) {
    audio.src = "./audio/latest.wav?v=" + Date.now();
    return "wav";
  }

  // MP3 Fallback
  const mp3OK = await fetch("./audio/latest.mp3", { method: "HEAD" })
    .then(r => r.ok)
    .catch(() => false);

  if (mp3OK) {
    audio.src = "./audio/latest.mp3?v=" + Date.now();
    return "mp3";
  }

  // Nichts vorhanden
  audio.removeAttribute("src");
  return "none";
}


// ---- JSON LOADER ------------------------------------------------

async function safeLoadJson(path) {
  return fetch(path + "?v=" + Date.now())
    .then(r => (r.ok ? r.json() : null))
    .catch(() => null);
}

export async function loadAllJson() {
  const status = await safeLoadJson("./data/self/status.json");
  const self = await safeLoadJson("./data/self/self-describe.json");
  const learning = await safeLoadJson("./data/self/learning.json");

  // UI aktualisieren
  if (status && status.daily_quote) {
    document.getElementById("quote").textContent = status.daily_quote;
  }

  if (self && self.physical) {
    document.getElementById("selfbox").innerHTML =
      `<b>Körper:</b> ${self.physical.description}<br>` +
      `<b>Stimme:</b> ${self.voice?.profile || "—"}<br>` +
      `<b>Affekt:</b> ${self.affect?.narrative || "—"}`;
  }

  if (learning && learning.next_focus) {
    document.getElementById("learningbox").textContent =
      "Nächster Fokus: " + learning.next_focus;
  }
}


// ---- INIT -------------------------------------------------------

export async function initApp() {
  await loadMedia();
  await loadAudio();
  await loadAllJson();

  // später: lipSync.init()
  console.log("Mira-App ist bereit");
    }
