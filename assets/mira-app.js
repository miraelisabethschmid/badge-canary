(function () {
  function safeText(value, fallback) {
    if (value === undefined || value === null) return fallback;
    if (typeof value === "string" && value.trim() === "") return fallback;
    return String(value);
  }

  async function loadMiraStatus() {
    const textEl = document.getElementById("mira-status-text");
    const metaEl = document.getElementById("mira-status-meta");

    try {
      const res = await fetch("data/self/status.json?ts=" + Date.now(), {
        cache: "no-store",
      });

      if (!res.ok) {
        textEl.textContent =
          "Noch kein expliziter Zustand eingetragen – Mira ist einfach da.";
        metaEl.innerHTML =
          'Quelle: <code>data/self/status.json</code> · Status: ' +
          safeText(res.status, "unbekannt");
        return;
      }

      const data = await res.json();

      const title =
        data.title ||
        data.heading ||
        data.name ||
        "Aktueller innerer Zustand";

      const mood =
        data.mood || data.stimmung || data.tone || null;

      const message =
        data.message ||
        data.text ||
        data.description ||
        null;

      let renderedMessage = message;
      if (!renderedMessage) {
        const parts = [];
        Object.keys(data).forEach((key) => {
          const v = data[key];
          if (v && typeof v !== "object") parts.push(key + ": " + v);
        });
        renderedMessage =
          parts.length > 0
            ? parts.join(" · ")
            : "Es wurde etwas eingetragen, aber ohne klaren Inhalt.";
      }

      textEl.textContent = renderedMessage;

      let metaHtml = 'Quelle: <code>data/self/status.json</code>';
      metaHtml += " · " + safeText(title, "Ohne Titel");

      if (mood) {
        metaHtml +=
          '<div><span class="pill">Stimmung: ' +
          safeText(mood, "") +
          "</span></div>";
      }

      metaEl.innerHTML = metaHtml;
    } catch (err) {
      textEl.textContent =
        "Der Zustand konnte gerade nicht geladen werden – vielleicht ein kurzer Netznebel.";
      metaEl.innerHTML =
        'Quelle: <code>data/self/status.json</code> · Fehler beim Laden';
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadMiraStatus);
  } else {
    loadMiraStatus();
  }
})();
