// assets/modules/audio.js
// Steuert Miras Stimme & Buttons (▶ / ⏸) und synchronisiert den Glow-Rahmen.
// Nutzt die IDs aus deiner aktuellen index.html.

export function initAudio() {
  const frame = document.getElementById("portrait-frame");
  const video = document.getElementById("portrait-video");
  const audioEl = document.getElementById("voice");
  const btnPlay = document.getElementById("btn-play");
  const btnPause = document.getElementById("btn-pause");
  const audioStatus = document.getElementById("audio-status");

  // Wenn irgendwas Wichtiges fehlt, still aussteigen
  if (!frame || !audioEl || !btnPlay || !btnPause || !audioStatus) {
    return;
  }

  let mediaType = "audio"; // "video" | "image" | "placeholder" | "audio"
  let audioReady = false;

  // Auf Event von assets.js hören (Video / Bild / Platzhalter)
  try {
    window.addEventListener("mira-media-ready", function (ev) {
      if (ev && ev.detail && ev.detail.mediaType) {
        mediaType = ev.detail.mediaType;
        // Wenn ein Video bereit ist, beschreiben wir das im Status
        if (mediaType === "video") {
          audioStatus.textContent =
            "Bereit — ▶ startet Video (mit Ton, sofern aktiviert).";
        } else if (mediaType === "image") {
          audioStatus.textContent =
            "Bereit — ▶ startet Audio zu Miras Porträt.";
        } else if (mediaType === "placeholder") {
          audioStatus.textContent =
            "Bereit — ▶ startet Audio, Bild/Video sind noch Platzhalter.";
        }
      }
    });
  } catch (_) {
    // Ignorieren, falls CustomEvent nicht verfügbar ist
  }

  // Audioquelle auswählen: WAV bevorzugt, sonst MP3
  function chooseAudioSource() {
    const canWav =
      audioEl.canPlayType("audio/wav") === "probably" ||
      audioEl.canPlayType("audio/wav") === "maybe";
    const canMp3 =
      audioEl.canPlayType("audio/mpeg") === "probably" ||
      audioEl.canPlayType("audio/mpeg") === "maybe";

    let chosen = null;

    if (canWav) {
      chosen = "audio/latest.wav";
    } else if (canMp3) {
      chosen = "audio/latest.mp3";
    }

    if (!chosen) {
      audioStatus.textContent =
        "Dein Browser unterstützt dieses Audioformat nicht.";
      return;
    }

    const ts = Date.now();
    audioEl.src = chosen + "?ts=" + ts;
    audioEl.load();
    audioStatus.textContent = "Lade Stimme …";
  }

  // Glow / Status mit Audio oder Video koppeln
  function attachMediaSpeakingEvents(element, labelPrefix) {
    if (!element) return;

    element.addEventListener("play", function () {
      frame.classList.remove("idle");
      frame.classList.add("speaking");
      audioStatus.textContent = labelPrefix + " spielt.";
    });

    element.addEventListener("pause", function () {
      frame.classList.remove("speaking");
      frame.classList.add("idle");
      audioStatus.textContent = labelPrefix + " pausiert.";
    });

    element.addEventListener("ended", function () {
      frame.classList.remove("speaking");
      frame.classList.add("idle");
      audioStatus.textContent =
        labelPrefix + " beendet – du kannst jederzeit erneut ▶ drücken.";
    });
  }

  attachMediaSpeakingEvents(audioEl, "Audio");
  attachMediaSpeakingEvents(video, "Video");

  // Wenn Audio bereit ist, Status setzen
  audioEl.addEventListener("canplaythrough", function () {
    if (!audioReady) {
      audioReady = true;
      if (mediaType === "video") {
        audioStatus.textContent =
          "Bereit — ▶ startet Video, Audio wird mitgeführt.";
      } else {
        audioStatus.textContent =
          "Bereit — ▶ startet Miras Stimme.";
      }
    }
  });

  audioEl.addEventListener("error", function () {
    audioStatus.textContent =
      "Audio konnte nicht geladen werden. Prüfe später noch einmal.";
  });

  // Buttons verbinden
  btnPlay.addEventListener("click", function () {
    // Wenn Video-Modus aktiv und ein Video-Element existiert
    if (mediaType === "video" && video) {
      // Video mit Ton abspielen
      try {
        // Falls du Audio nur über das Video spielen willst:
        // audioEl.muted = true; // optional
        video.muted = false; // falls Ton im Video enthalten ist
      } catch (_) {}

      video
        .play()
        .then(function () {
          // Falls du gleichzeitig das separate Audio NICHT willst, kannst du hier audioEl.pause() setzen.
        })
        .catch(function (err) {
          audioStatus.textContent =
            "Video konnte nicht automatisch starten – bitte erneut ▶ tippen.";
          console.error(err);
        });
      return;
    }

    // Standard: Audio-only
    audioEl
      .play()
      .then(function () {
        // Alles gut
      })
      .catch(function () {
        audioStatus.textContent =
          "Audio konnte nicht automatisch starten — bitte erneut ▶ tippen oder Browser-Einstellungen prüfen.";
      });
  });

  btnPause.addEventListener("click", function () {
    // Beide stoppen, damit nichts „weiterläuft“
    if (video && !video.paused) {
      video.pause();
    }
    if (!audioEl.paused) {
      audioEl.pause();
    }
  });

  // Initial starten wir mit der Wahl der Audioquelle
  chooseAudioSource();

  // Anfangszustand
  audioStatus.textContent = "Bereit, sobald du ▶ tippst.";
}
