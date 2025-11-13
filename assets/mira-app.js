// assets/mira-app.js
// Zentrale Steuerung:
// - Zeitstempel
// - Status / Selbstbild / Lernen
// - Bild / Video / Audio (Play/Pause)

(function () {
  // ----------- kleine Helfer -----------

  async function fetchJson(path) {
    try {
      const res = await fetch(path + "?v=" + Date.now());
      if (!res.ok) throw new Error("HTTP " + res.status);
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  function $(id) {
    return document.getElementById(id);
  }

  const liveTsEl           = $("live-timestamp");

  const portraitFrame      = $("portrait-frame");
  const portraitVideo      = $("portrait-video");
  const portraitImg        = $("portrait-img");
  const portraitPlaceholder= $("portrait-placeholder");
  const imageMeta          = $("image-meta");
  const imageStatus        = $("image-status");

  const audioEl            = $("voice");
  const btnPlay            = $("btn-play");
  const btnPause           = $("btn-pause");
  const audioStatus        = $("audio-status");

  const quoteText          = $("quote-text");
  const baseTone           = $("base-tone");
  const quoteUpdated       = $("quote-updated");
  const toneTag            = $("tone-tag");
  const toneTagLabel       = $("tone-tag-label");

  const selfimageSummary   = $("selfimage-summary");
  const learningSummary    = $("learning-summary");
  const versionPill        = $("version-pill");

  let videoAvailable = false;

  // ----------- Zeitstempel -----------

  function updateLiveTimestamp() {
    const now = new Date();
    const iso = now.toISOString().replace(/\.\d+Z$/, "Z");
    if (liveTsEl) liveTsEl.textContent = iso;
  }

  // ----------- Thema / Farben nach Grundton -----------

  function applyToneTheme(toneRaw) {
    if (!toneRaw) return;
    const tone = String(toneRaw).toLowerCase();

    let accent   = "#3ce081";
    let accentSoft = "rgba(60, 224, 129, 0.26)";
    let bgMain   = "radial-gradient(circle at top, #151f3b 0%, #050813 55%, #02030a 100%)";
    let cardBg   = "linear-gradient(145deg, rgba(255,255,255,0.07), rgba(7,10,24,0.95))";
    let label    = toneRaw;

    if (tone.includes("ruhig") || tone.includes("klar") || tone.includes("still")) {
      accent     = "#3fb7ff";
      accentSoft = "rgba(63,183,255,0.26)";
      bgMain     = "radial-gradient(circle at top, #0c1830 0%, #020615 55%, #02030a 100%)";
      label      = toneRaw + " · klarer Himmel";
    } else if (tone.includes("warm") || tone.includes("zugewandt") || tone.includes("sanft")) {
      accent     = "#ffb74d";
      accentSoft = "rgba(255,183,77,0.26)";
      bgMain     = "radial-gradient(circle at top, #28140a 0%, #12080a 55%, #030108 100%)";
      label      = toneRaw + " · goldene Stunde";
    } else if (tone.includes("intensiv") || tone.includes("lebendig") || tone.includes("kraftvoll")) {
      accent     = "#ff6fa8";
      accentSoft = "rgba(255,111,168,0.28)";
      bgMain     = "radial-gradient(circle at top, #2b0620 0%, #100411 55%, #05000a 100%)";
      label      = toneRaw + " · hohe Energie";
    } else if (tone.includes("melanchol")) {
      accent     = "#8e9cff";
      accentSoft = "rgba(142,156,255,0.3)";
      bgMain     = "radial-gradient(circle at top, #0f1028 0%, #060616 55%, #020107 100%)";
      label      = toneRaw + " · leise Tiefe";
    }

    const root = document.documentElement;
    root.style.setProperty("--accent", accent);
    root.style.setProperty("--accent-soft", accentSoft);
    root.style.setProperty("--bg-main", bgMain);
    root.style.setProperty("--card-bg", cardBg);

    if (toneTag && toneTagLabel) {
      toneTag.style.display = "inline-flex";
      toneTagLabel.textContent = label;
    }
  }

  // ----------- Status / Tagesimpuls -----------

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

  // ----------- Selbstbild / Entwicklung -----------

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
      data.next_step  ||
      data.note       ||
      "";
    if (learningSummary) {
      learningSummary.textContent = next
        ? "Aktueller Lernfokus: " + next
        : "Lernstatus vorhanden, aber ohne klaren Fokus-Text.";
    }
  }

  // ----------- Medien: Video → Bild → Platzhalter -----------

  function initMedia() {
    // 1) Bild (stabiler Kernweg)
    if (!portraitImg || !portraitPlaceholder) return;

    const paths = [
      "data/self/latest_image.png",
      "data/self/latest_image.svg"
    ];
    let index = 0;

    function tryNext() {
      if (index >= paths.length) {
        portraitImg.style.display = "none";
        portraitPlaceholder.style.display = "flex";
        portraitPlaceholder.textContent = "Kein aktuelles Bild gefunden.";
        if (imageMeta)   imageMeta.textContent   = "Medium: —";
        if (imageStatus) imageStatus.textContent = "Status: kein Bild vorhanden";
        return;
      }

      const src = paths[index] + "?v=" + Date.now();
      if (imageStatus) imageStatus.textContent = "Status: lade " + paths[index] + " …";

      portraitImg.onload = function () {
        portraitPlaceholder.style.display = "none";
        portraitImg.style.display = "block";
        if (imageMeta)   imageMeta.textContent   = "Medium: Bild (" + paths[index] + ")";
        if (imageStatus) imageStatus.textContent = "Status: Bild erfolgreich geladen";
      };

      portraitImg.onerror = function () {
        index += 1;
        tryNext();
      };

      portraitImg.src = src;
    }

    tryNext();

    // 2) Falls später einmal Video genutzt wird, können wir das ergänzen,
    // aber aktuell ist Bild + Audio der stabile Kern.
  }

  // ----------- Audio (Play/Pause + Frame-Animation) -----------

  function setupAudio() {
    if (!audioEl || !btnPlay || !btnPause) return;

    audioEl.addEventListener("canplaythrough", function () {
      if (audioStatus) {
        audioStatus.textContent = "Bereit — Tippe ▶, damit Mira spricht.";
      }
    });

    btnPlay.addEventListener("click", function () {
      audioEl
        .play()
        .then(function () {
          if (audioStatus) audioStatus.textContent = "Spielt.";
        })
        .catch(function () {
          if (audioStatus) {
            audioStatus.textContent =
              "Audio konnte nicht automatisch starten — bitte erneut ▶ tippen oder Browser-Einstellungen prüfen.";
          }
        });
    });

    btnPause.addEventListener("click", function () {
      audioEl.pause();
    });

    function attachSpeakingEvents(el, label) {
      if (!el) return;
      el.addEventListener("play", function () {
        if (portraitFrame) {
          portraitFrame.classList.remove("idle");
          portraitFrame.classList.add("speaking");
        }
        if (audioStatus) audioStatus.textContent = label + " spielt.";
      });
      el.addEventListener("pause", function () {
        if (portraitFrame) {
          portraitFrame.classList.remove("speaking");
          portraitFrame.classList.add("idle");
        }
        if (audioStatus) audioStatus.textContent = label + " pausiert.";
      });
      el.addEventListener("ended", function () {
        if (portraitFrame) {
          portraitFrame.classList.remove("speaking");
          portraitFrame.classList.add("idle");
        }
        if (audioStatus) {
          audioStatus.textContent =
            label + " beendet – du kannst jederzeit erneut ▶ drücken.";
        }
      });
    }

    attachSpeakingEvents(audioEl, "Audio");
  }

  // ----------- Start -----------

  function init() {
    updateLiveTimestamp();
    initMedia();
    setupAudio();
    loadStatus();
    loadSelfImage();
    loadLearning();

    // Live-Timestamp alle 30 Sekunden aktualisieren
    setInterval(updateLiveTimestamp, 30000);
  }

  // Warten, bis DOM steht
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
