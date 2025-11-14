// assets/modules/assets.js
// Medien-Logik für Mira: Video → Bild → Platzhalter
// funktioniert mit den IDs aus deiner aktuellen index.html

export function initMedia() {
  const frame = document.getElementById("portrait-frame");
  const video = document.getElementById("portrait-video");
  const img = document.getElementById("portrait-img");
  const placeholder = document.getElementById("portrait-placeholder");
  const meta = document.getElementById("image-meta");
  const status = document.getElementById("image-status");

  // Wenn die Elemente nicht existieren, still aussteigen
  if (!frame || !video || !img || !placeholder || !meta || !status) {
    return;
  }

  // Grundzustand
  placeholder.style.display = "flex";
  img.style.display = "none";
  video.style.display = "none";
  meta.textContent = "Medium: —";
  status.textContent = "Status: lade Video …";

  const VIDEO_PATH = "data/self/latest_video.mp4";
  const IMAGE_PATHS = [
    "data/self/latest_image.png",
    "data/mira-placeholder.svg"
  ];

  let imageTriedIndex = 0;
  let mediaType = "placeholder"; // "video" | "image" | "placeholder"

  function setMediaType(newType) {
    mediaType = newType;
    // Globales Event, damit avatar.js o.ä. später reagieren kann
    try {
      window.dispatchEvent(
        new CustomEvent("mira-media-ready", {
          detail: { mediaType: newType }
        })
      );
    } catch (_) {
      // ignorieren, falls CustomEvent nicht unterstützt
    }
  }

  function showPlaceholder(message) {
    video.style.display = "none";
    img.style.display = "none";
    placeholder.style.display = "flex";
    placeholder.textContent = message || "Kein Medium verfügbar.";
    meta.textContent = "Medium: —";
    status.textContent = "Status: Platzhalter aktiv";
    setMediaType("placeholder");
  }

  function tryLoadNextImage() {
    if (imageTriedIndex >= IMAGE_PATHS.length) {
      showPlaceholder("Kein aktuelles Bild gefunden.");
      return;
    }

    const path = IMAGE_PATHS[imageTriedIndex];
    imageTriedIndex += 1;

    video.style.display = "none";
    img.style.display = "none";
    placeholder.style.display = "flex";
    placeholder.textContent = "Lade Bild …";
    meta.textContent = "Medium: —";
    status.textContent = "Status: lade " + path + " …";

    const ts = Date.now();
    img.onload = function () {
      placeholder.style.display = "none";
      img.style.display = "block";
      video.style.display = "none";
      meta.textContent = "Medium: Bild (" + path + ")";
      status.textContent = "Status: Bild erfolgreich geladen";
      setMediaType("image");
    };

    img.onerror = function () {
      // nächstes Bild / Platzhalter probieren
      tryLoadNextImage();
    };

    img.src = path + "?ts=" + ts;
  }

  function initVideo() {
    // Sicherstellen, dass Event-Handler gesetzt sind, bevor wir src setzen
    video.preload = "metadata";
    video.muted = true;
    video.playsInline = true;
    video.loop = false; // Du kannst das später ändern, falls du Loop möchtest

    const ts = Date.now();
    const srcWithTs = VIDEO_PATH + "?ts=" + ts;

    // Event: Video konnte geladen werden
    function onLoadedData() {
      video.removeEventListener("loadeddata", onLoadedData);
      video.removeEventListener("error", onError);
      video.removeEventListener("stalled", onStalled);

      placeholder.style.display = "none";
      img.style.display = "none";
      video.style.display = "block";

      meta.textContent = "Medium: Video (" + VIDEO_PATH + ")";
      status.textContent = "Status: Video bereit";

      setMediaType("video");
    }

    // Event: es gab direkt einen Fehler beim Laden
    function onError() {
      video.removeEventListener("loadeddata", onLoadedData);
      video.removeEventListener("error", onError);
      video.removeEventListener("stalled", onStalled);
      status.textContent = "Status: Video konnte nicht geladen werden – Bild-Fallback.";
      tryLoadNextImage();
    }

    // Event: gestallt / hängt – als Soft-Fallback nach 15s
    function onStalled() {
      // Soft-Fallback nur, wenn wirklich sehr lange nichts passiert
      setTimeout(function () {
        if (video.readyState < 2) {
          // Noch immer keine Daten → wie Fehler behandeln
          onError();
        }
      }, 15000);
    }

    video.addEventListener("loadeddata", onLoadedData);
    video.addEventListener("error", onError);
    video.addEventListener("stalled", onStalled);

    // Jetzt Quelle setzen und Laden anstoßen
    status.textContent = "Status: versuche Video zu laden …";
    meta.textContent = "Medium: Video (wird geprüft)";
    video.src = srcWithTs;
    // kein .play() hier, das macht später audio.js oder ein Button, falls gewünscht
  }

  // Initial starten wir mit dem Versuch, Video zu laden
  initVideo();
      }
