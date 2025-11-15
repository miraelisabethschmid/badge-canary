// assets/modules/audio.js
// Audio-Logik: WAV/MP3-Fallback + Play/Pause + Status + Rahmen-Animation

export function initAudio() {
  const audioEl = document.getElementById("voice");
  const btnPlay = document.getElementById("btn-play");
  const btnPause = document.getElementById("btn-pause");
  const statusEl = document.getElementById("audio-status");
  const frame = document.getElementById("portrait-frame");

  if (!audioEl || !btnPlay || !btnPause || !statusEl || !frame) {
    console.warn("[audio] Wichtige Elemente fehlen, Audio-Modul wird nicht initialisiert.");
    return;
  }

  let ready = false;

  // -----------------------------------
  // FORMATWAHL: WAV → MP3
  // -----------------------------------
  function chooseSource() {
    const wavSupport = audioEl.canPlayType("audio/wav");
    const mp3Support = audioEl.canPlayType("audio/mpeg");

    if (wavSupport === "probably" || wavSupport === "maybe") {
      audioEl.src = "audio/latest.wav?ts=" + Date.now();
      statusEl.textContent = "Audioquelle: latest.wav (bereit, sobald du ▶ tippst).";
    } else if (mp3Support === "probably" || mp3Support === "maybe") {
      audioEl.src = "audio/latest.mp3?ts=" + Date.now();
      statusEl.textContent = "Audioquelle: latest.mp3 (bereit, sobald du ▶ tippst).";
    } else {
      statusEl.textContent = "Dein Browser unterstützt das Audioformat nicht.";
    }
  }

  chooseSource();

  // -----------------------------------
  // BEREIT-SIGNAL
  // -----------------------------------
  audioEl.addEventListener("canplaythrough", () => {
    ready = true;
    if (!audioEl.paused) return;
    statusEl.textContent = "Bereit – tippe ▶, damit Mira spricht.";
    window.dispatchEvent(
      new CustomEvent("mira-audio-ready", { detail: { src: audioEl.src } })
    );
  });

  audioEl.addEventListener("error", () => {
    ready = false;
    statusEl.textContent =
      "Audio konnte nicht geladen werden – prüfe später noch einmal.";
  });

  // -----------------------------------
  // RAHMEN-ANIMATION (Sprechen)
  // -----------------------------------
  function setSpeaking(isSpeaking, label) {
    if (isSpeaking) {
      frame.classList.remove("idle");
      frame.classList.add("speaking");
    } else {
      frame.classList.remove("speaking");
      frame.classList.add("idle");
    }
    if (label) {
      statusEl.textContent = label;
    }
  }

  audioEl.addEventListener("play", () => {
    setSpeaking(true, "Mira spricht gerade …");
  });

  audioEl.addEventListener("pause", () => {
    if (audioEl.currentTime > 0 && !audioEl.ended) {
      setSpeaking(false, "Mira macht eine Pause.");
    }
  });

  audioEl.addEventListener("ended", () => {
    setSpeaking(false, "Wiedergabe beendet – du kannst jederzeit erneut ▶ drücken.");
  });

  // -----------------------------------
  // BUTTONS: PLAY / PAUSE
  // -----------------------------------
  btnPlay.addEventListener("click", () => {
    if (!ready) {
      // Falls der Browser noch lädt, trotzdem versuchen zu starten
      statusEl.textContent = "Lade Audio … bitte kurz warten.";
    }

    audioEl
      .play()
      .then(() => {
        // Erfolg – Status wird von 'play'-Event gesetzt
      })
      .catch((err) => {
        console.warn("[audio] Wiedergabe blockiert:", err);
        statusEl.textContent =
          "Audio konnte nicht automatisch starten – bitte ▶ noch einmal tippen oder Browser-Einstellungen prüfen.";
      });
  });

  btnPause.addEventListener("click", () => {
    if (!audioEl.paused) {
      audioEl.pause();
      // Status wird vom 'pause'-Event gesetzt
    } else {
      statusEl.textContent = "Audio ist bereits pausiert.";
    }
  });
}
