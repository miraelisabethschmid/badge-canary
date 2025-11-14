// assets/modules/json.js
// Lädt Status (Tagesimpuls), Selbstbild & Lernfokus aus JSON
// und passt die Farb-Stimmung der Seite an.

export function initJson() {
  const quoteText = document.getElementById("quote-text");
  const baseTone = document.getElementById("base-tone");
  const quoteUpdated = document.getElementById("quote-updated");
  const toneTag = document.getElementById("tone-tag");
  const toneTagLabel = document.getElementById("tone-tag-label");

  const selfimageSummary = document.getElementById("selfimage-summary");
  const learningSummary = document.getElementById("learning-summary");
  const versionPill = document.getElementById("version-pill");

  // Wenn wichtige Elemente fehlen, brechen wir still ab
  if (
    !quoteText ||
    !baseTone ||
    !quoteUpdated ||
    !toneTag ||
    !toneTagLabel ||
    !selfimageSummary ||
    !learningSummary ||
    !versionPill
  ) {
    return;
  }

  // Hilfsfunktion: JSON sicher laden
  function safeFetchJson(path, onSuccess, onError) {
    const url = path + "?ts=" + Date.now();
    fetch(url)
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

  // Farb-Stimmung je nach Grundton
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
      accentSoft = "rgba(142,156,255,0.3)";
      bgMain =
        "radial-gradient(circle at top, #0f1028 0%, #060616 55%, #020107 100%)";
      label = toneRaw + " · leise Tiefe";
    }

    document.documentElement.style.setProperty("--accent", accent);
    document.documentElement.style.setProperty("--accent-soft", accentSoft);
    document.documentElement.style.setProperty("--bg-main", bgMain);
    document.documentElement.style.setProperty("--card-bg", cardBg);

    toneTag.style.display = "inline-flex";
    toneTagLabel.textContent = label;
  }

  // 1) Status / Tagesimpuls laden
  function loadStatus() {
    safeFetchJson(
      "data/self/status.json",
      function (data) {
        if (data && typeof data === "object") {
          quoteText.textContent =
            data.daily_quote || "Noch kein Tagesimpuls eingetragen.";
          const tone = data.base_tone || "unbestimmt";
          baseTone.textContent = tone;
          quoteUpdated.textContent = data.updated_at || "—";
          applyToneTheme(tone);
        } else {
          quoteText.textContent = "Noch kein Tagesimpuls eingetragen.";
          baseTone.textContent = "unbestimmt";
          quoteUpdated.textContent = "—";
        }
      },
      function () {
        quoteText.textContent = "Noch kein Tagesimpuls eingetragen.";
        baseTone.textContent = "unbestimmt";
        quoteUpdated.textContent = "—";
      }
    );
  }

  // 2) Selbstbild / Portrait-State laden
  function loadSelfImage() {
    safeFetchJson(
      "data/self/portrait_state.json",
      function (data) {
        if (data && typeof data === "object") {
          const summary =
            data.summary ||
            data.description ||
            data.current_self_image ||
            "";
          const evo = data.evolution_note || data.trajectory || "";

          let text = "";
          if (summary) text += summary;
          if (evo) text += (text ? " " : "") + evo;

          if (!text) {
            text =
              "Daten zum Selbstbild sind vorhanden, aber ohne Kurzbeschreibung.";
          }

          selfimageSummary.textContent = text;

          const version = data.version || data.portrait_version || "";
          if (version) {
            versionPill.style.display = "inline-block";
            versionPill.textContent = "Selbstbild-Version: " + version;
          } else {
            versionPill.style.display = "none";
          }
        } else {
          selfimageSummary.textContent =
            "Noch kein explizites Selbstbild hinterlegt.";
          versionPill.style.display = "none";
        }
      },
      function () {
        selfimageSummary.textContent =
          "Noch kein explizites Selbstbild hinterlegt.";
        versionPill.style.display = "none";
      }
    );
  }

  // 3) Lernstatus laden
  function loadLearning() {
    safeFetchJson(
      "data/self/learning.json",
      function (data) {
        if (data && typeof data === "object") {
          const next =
            data.next_focus || data.next_step || data.note || data.summary || "";
          if (next) {
            learningSummary.textContent = "Aktueller Lernfokus: " + next;
          } else {
            learningSummary.textContent =
              "Lernstatus vorhanden, aber ohne klaren Fokus-Text.";
          }
        } else {
          learningSummary.textContent = "Noch kein Lernstatus hinterlegt.";
        }
      },
      function () {
        learningSummary.textContent = "Noch kein Lernstatus hinterlegt.";
      }
    );
  }

  // Initial laden
  loadStatus();
  loadSelfImage();
  loadLearning();

  // Optional: alle 60 Sekunden aktualisieren
  setInterval(function () {
    loadStatus();
    loadSelfImage();
    loadLearning();
  }, 60000);
}
