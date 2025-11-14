// assets/modules/json.js
// Lädt Status, Selbstbild & Lernen aus JSON
// und passt die Farb-Stimmung an den Grundton an.

export function initJson() {
  const quoteText = document.getElementById("quote-text");
  const baseTone = document.getElementById("base-tone");
  const quoteUpdated = document.getElementById("quote-updated");
  const toneTag = document.getElementById("tone-tag");
  const toneTagLabel = document.getElementById("tone-tag-label");

  const selfimageSummary = document.getElementById("selfimage-summary");
  const learningSummary = document.getElementById("learning-summary");
  const versionPill = document.getElementById("version-pill");

  if (
    !quoteText ||
    !baseTone ||
    !quoteUpdated ||
    !toneTag ||
    !toneTagLabel ||
    !selfimageSummary ||
    !learningSummary
  ) {
    console.warn("[json] Wichtige DOM-Elemente fehlen – Modul läuft eingeschränkt.");
  }

  // -------------------------------
  // Farb-Stimmung aus Grundton
  // -------------------------------
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
      accentSoft = "rgba(142,156,255,0.3)";
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

  // -------------------------------
  // JSON-Helper
  // -------------------------------
  function safeFetchJson(path, onSuccess, onError) {
    fetch(path + "?v=" + Date.now())
      .then(function (res) {
        if (!res.ok) {
          throw new Error("HTTP " + res.status);
        }
        return res.json();
      })
      .then(onSuccess)
      .catch(function (err) {
        if (onError) onError(err);
      });
  }

  // -------------------------------
  // 1) Status / Tagesimpuls
  // -------------------------------
  function loadStatus() {
    safeFetchJson(
      "data/self/status.json",
      function (data) {
        if (!data || typeof data !== "object") {
          if (quoteText) {
            quoteText.textContent = "Noch kein Tagesimpuls eingetragen.";
          }
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

        window.dispatchEvent(
          new CustomEvent("mira-status-updated", { detail: data })
        );
      },
      function () {
        if (quoteText) {
          quoteText.textContent = "Noch kein Tagesimpuls eingetragen.";
        }
        if (baseTone) baseTone.textContent = "unbestimmt";
        if (quoteUpdated) quoteUpdated.textContent = "—";
      }
    );
  }

  // -------------------------------
  // 2) Selbstbild / Portrait-State
  // -------------------------------
  function loadSelfImage() {
    safeFetchJson(
      "data/self/portrait_state.json",
      function (data) {
        if (!data || typeof data !== "object") {
          if (selfimageSummary) {
            selfimageSummary.textContent =
              "Noch kein explizites Selbstbild hinterlegt.";
          }
          if (versionPill) versionPill.style.display = "none";
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

        if (selfimageSummary) {
          selfimageSummary.textContent = text;
        }

        const version = data.version || data.portrait_version || "";
        if (versionPill) {
          if (version) {
            versionPill.style.display = "inline-block";
            versionPill.textContent = "Selbstbild-Version: " + version;
          } else {
            versionPill.style.display = "none";
          }
        }

        window.dispatchEvent(
          new CustomEvent("mira-selfimage-updated", { detail: data })
        );
      },
      function () {
        if (selfimageSummary) {
          selfimageSummary.textContent =
            "Noch kein explizites Selbstbild hinterlegt.";
        }
        if (versionPill) versionPill.style.display = "none";
      }
    );
  }

  // -------------------------------
  // 3) Lernen / Entwicklungs-Fokus
  // -------------------------------
  function loadLearning() {
    safeFetchJson(
      "data/self/learning.json",
      function (data) {
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
          "";

        if (next && learningSummary) {
          learningSummary.textContent = "Aktueller Lernfokus: " + next;
        } else if (learningSummary) {
          learningSummary.textContent =
            "Lernstatus vorhanden, aber ohne klaren Fokus-Text.";
        }

        window.dispatchEvent(
          new CustomEvent("mira-learning-updated", { detail: data })
        );
      },
      function () {
        if (learningSummary) {
          learningSummary.textContent = "Noch kein Lernstatus hinterlegt.";
        }
      }
    );
  }

  // -------------------------------
  // Initial laden + sanftes Polling
  // -------------------------------
  loadStatus();
  loadSelfImage();
  loadLearning();

  // Alle 60 Sekunden neu einlesen (leicht, aber lebendig)
  setInterval(function () {
    loadStatus();
    loadSelfImage();
    loadLearning();
  }, 60000);
}
