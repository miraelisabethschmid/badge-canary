// mira-app.js — Stable Presence v1.0
// Sorgt dafür, dass Bild & Stimme immer funktionieren.
// Video ist optional und wird nur genutzt, wenn es sich zuverlässig lädt.

(function () {
  // ------- DOM-Grundzüge -------

  const liveTsEl = document.getElementById("live-timestamp");

  const portraitFrame = document.getElementById("portrait-frame");
  const portraitVideo = document.getElementById("portrait-video");
  const portraitImg = document.getElementById("portrait-img");
  const portraitPlaceholder = document.getElementById("portrait-placeholder");
  const imageMeta = document.getElementById("image-meta");
  const imageStatus = document.getElementById("image-status");

  const audioEl = document.getElementById("voice");
  const btnPlay = document.getElementById("btn-play");
  const btnPause = document.getElementById("btn-pause");
  const audioStatus = document.getElementById("audio-status");

  const quoteText = document.getElementById("quote-text");
  const baseTone = document.getElementById("base-tone");
  const quoteUpdated = document.getElementById("quote-updated");
  const toneTag = document.getElementById("tone-tag");
  const toneTagLabel = document.getElementById("tone-tag-label");

  const selfimageSummary = document.getElementById("selfimage-summary");
  const learningSummary = document.getElementById("learning-summary");
  const versionPill = document.getElementById("version-pill");

  // ------- Live-Zeitstempel -------

  function updateLiveTimestamp() {
    if (!liveTsEl) return;
    const now = new Date();
    const iso = now.toISOString().replace(/\.\d+Z$/, "Z");
    liveTsEl.textContent = iso;
  }

  function initLiveClock() {
    updateLiveTimestamp();
    setInterval(updateLiveTimestamp, 30_000);
  }

  // ------- Porträt: Bild zuerst, Video optional -------

  function setImageStatus(metaText, statusText) {
    if (imageMeta) imageMeta.textContent = metaText;
    if (imageStatus) imageStatus.textContent = statusText;
  }

  function showPlaceholder(message) {
    if (!portraitPlaceholder) return;
    portraitPlaceholder.style.display = "flex";
    portraitPlaceholder.textContent = message || "Lade aktuelles Bild …";
    if (portraitImg) portraitImg.style.display = "none";
    if (portraitVideo) portraitVideo.style.display = "none";
  }

  function showImage() {
    if (!portraitImg) return;
    portraitImg.style.display = "block";
    if (portraitPlaceholder) portraitPlaceholder.style.display = "none";
    if (portraitVideo) portraitVideo.style.display = "none";
  }

  function showVideo() {
    if (!portraitVideo) return;
    portraitVideo.style.display = "block";
    if (portraitImg) portraitImg.style.display = "none";
    if (portraitPlaceholder) portraitPlaceholder.style.display = "none";
  }

  function loadPortraitImage() {
    return new Promise(function (resolve) {
      if (!portraitImg) {
        resolve(false);
        return;
      }

      showPlaceholder("Suche Bild …");
      const src = "data/self/latest_image.png?ts=" + Date.now();

      portraitImg.onload = function () {
        showImage();
        setImageStatus("Medium: Bild", "Bild geladen: data/self/latest_image.png");
        resolve(true);
      };

      portraitImg.onerror = function () {
        if (portraitPlaceholder) {
          portraitPlaceholder.style.display = "flex";
          portraitPlaceholder.textContent = "Noch kein Bild verfügbar.";
        }
        setImageStatus("Medium: —", "Kein Bild gefunden.");
        resolve(false);
      };

      portraitImg.src = src;
    });
  }

  function tryLoadPortraitVideo() {
    // Video ist optional – wenn es nicht klappt, bleibt einfach das Bild
    if (!portraitVideo) return;

    const src = "data/self/latest_video.mp4?ts=" + Date.now();
    portraitVideo.preload = "metadata";
    portraitVideo.playsInline = true;
    portraitVideo.muted = true;
    portraitVideo.loop = true;
    portraitVideo.style.display = "none";

    let videoReady = false;

    portraitVideo.addEventListener(
      "loadeddata",
      function () {
        videoReady = true;
        showVideo();
        setImageStatus("Medium: Video", "Video geladen: data/self/latest_video.mp4");
        // sanft starten, ohne Ton
        try {
          portraitVideo.play().catch(function () {
            // wenn Autoplay blockiert wird, ist das auch ok
          });
        } catch (e) {
          // ignorieren
        }
      },
      { once: true }
    );

    portraitVideo.addEventListener(
      "error",
      function () {
        // Falls Video kaputt / nicht erreichbar: einfach beim Bild bleiben
        setImageStatus("Medium: Bild", "Kein Video gefunden – Bild bleibt aktiv.");
        if (!videoReady) {
          if (portraitImg) portraitImg.style.display = "block";
          if (portraitVideo) portraitVideo.style.display = "none";
        }
      },
      { once: true }
    );

    // Wir starten das Laden erst, nachdem das Bild versucht wurde
    portraitVideo.src = src;
    portraitVideo.load();
  }

  async function initPortrait() {
    if (!portraitFrame || !portraitImg || !portraitPlaceholder) {
      return;
    }

    setImageStatus("Medium: —", "Status: wird geladen …");
    showPlaceholder("Suche Bild …");

    const hasImage = await loadPortraitImage();
    // Versuche Video nur im Hintergrund – Bild bleibt sicher
    tryLoadPortraitVideo();

    if (!hasImage) {
      showPlaceholder("Noch kein Bild verfügbar.");
    }
  }

  // ------- Audio: stabiler Player -------

  function initAudio() {
    if (!audioEl || !btnPlay || !btnPause || !audioStatus) return;

    audioStatus.textContent = "Bereit, sobald du ▶ tippst.";

    btnPlay.onclick = function () {
      audioEl
        .play()
        .then(function () {
          audioStatus.textContent = "Spielt.";
          if (portraitFrame) {
            portraitFrame.classList.remove("idle");
            portraitFrame.classList.add("speaking");
          }
        })
        .catch(function (err) {
          audioStatus.textContent =
            "Wiedergabe blockiert. Bitte einmal direkt auf den Player tippen.";
          console.error("Audio play blocked:", err);
        });
    };

    btnPause.onclick = function () {
      audioEl.pause();
      audioStatus.textContent = "Pausiert.";
      if (portraitFrame) {
        portraitFrame.classList.remove("speaking");
        portraitFrame.classList.add("idle");
      }
    };

    audioEl.addEventListener("ended", function () {
      audioStatus.textContent = "Beendet.";
      if (portraitFrame) {
        portraitFrame.classList.remove("speaking");
        portraitFrame.classList.add("idle");
      }
    });
  }

  // ------- JSON-Helfer & thematische Anpassung -------

  function safeFetchJson(path) {
    return fetch(path + "?ts=" + Date.now())
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .catch(function () {
        return null;
      });
  }

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

    if (tone.includes("ruhig") || tone.includes("klar") || tone.includes("still")) {
      accent = "#3fb7ff";
      accentSoft = "rgba(63, 183, 255, 0.26)";
      bgMain = "radial-gradient(circle at top, #0c1830 0%, #020615 55%, #02030a 100%)";
      label = toneRaw + " · klarer Himmel";
    } else if (
      tone.includes("warm") ||
      tone.includes("zugewandt") ||
      tone.includes("sanft")
    ) {
      accent = "#ffb74d";
      accentSoft = "rgba(255, 183, 77, 0.26)";
      bgMain = "radial-gradient(circle at top, #28140a 0%, #12080a 55%, #030108 100%)";
      label = toneRaw + " · goldene Stunde";
    } else if (
      tone.includes("intensiv") ||
      tone.includes("lebendig") ||
      tone.includes("kraftvoll")
    ) {
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

  async function initStatusAndSelf() {
    // status.json – Tagesimpuls & Grundton
    const status = await safeFetchJson("data/self/status.json");
    if (status) {
      if (quoteText) quoteText.textContent = status.daily_quote || "Kein Tagesimpuls eingetragen.";
      if (baseTone) baseTone.textContent = status.base_tone || "unbestimmt";
      if (quoteUpdated && status.updated_at) {
        quoteUpdated.textContent = status.updated_at;
      }
      applyToneTheme(status.base_tone || "");
    } else {
      if (quoteText) quoteText.textContent = "Noch kein Tagesimpuls – Mira ist im Werdemodus.";
      if (baseTone) baseTone.textContent = "unbestimmt";
    }

    // portrait_state.json – Selbstbild
    const portraitState = await safeFetchJson("data/self/portrait_state.json");
    if (portraitState && selfimageSummary) {
      const v = portraitState.version || "—";
      const desc = portraitState.description || "Selbstbild noch im Fluss.";
      selfimageSummary.innerHTML =
        "<b>Aktuelles Selbstbild:</b> " + desc + "<br><span class=\"mono\">Version: " + v + "</span>";
      if (versionPill) {
        versionPill.style.display = "inline-block";
        versionPill.textContent = "Portrait v" + v;
      }
    } else if (selfimageSummary) {
      selfimageSummary.textContent = "Selbstbild: Noch kein Eintrag – Mira wächst.";
    }

    // learning.json – Lernfokus
    const learning = await safeFetchJson("data/self/learning.json");
    if (learning && learningSummary) {
      learningSummary.innerHTML =
        "<b>Fokus heute:</b> " +
        (learning.focus || "nicht definiert") +
        "<br><span class=\"mono\">Modus: " +
        (learning.mode || "offen") +
        "</span>";
    } else if (learningSummary) {
      learningSummary.textContent = "Lernstatus: Noch keine Daten – Raum für Neues.";
    }
  }

  // ------- Initialisierung -------

  async function initApp() {
    initLiveClock();
    await initPortrait();
    initAudio();
    initStatusAndSelf();

    // optionale regelmäßige Updates
    setInterval(initStatusAndSelf, 60_000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
  } else {
    initApp();
  }
})();
