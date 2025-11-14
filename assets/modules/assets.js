// assets/modules/assets.js
// Video → Bild → Platzhalter (robust, GitHub Pages freundlich)

export function initMedia() {
  const video = document.getElementById("portrait-video");
  const img = document.getElementById("portrait-img");
  const placeholder = document.getElementById("portrait-placeholder");

  const metaEl = document.getElementById("image-meta");
  const statusEl = document.getElementById("image-status");

  // Initialer Zustand
  let mode = "placeholder";
  placeholder.style.display = "block";
  img.style.display = "none";
  video.style.display = "none";

  statusEl.textContent = "Status: lädt …";

  // -----------------------------------
  // VIDEO LADEN
  // -----------------------------------
  const videoSrc = "data/self/latest_video.mp4?ts=" + Date.now();

  // Video vorbereiten
  video.preload = "metadata";
  video.src = videoSrc;

  video.addEventListener("loadeddata", () => {
    // Video erfolgreich geladen
    mode = "video";
    video.style.display = "block";
    img.style.display = "none";
    placeholder.style.display = "none";

    metaEl.textContent = "Medium: Video";
    statusEl.textContent = "Status: Video aktiv";

    window.dispatchEvent(
      new CustomEvent("mira-media-ready", { detail: { mediaType: "video" } })
    );
  });

  video.addEventListener("error", () => {
    // Video konnte NICHT geladen werden → Bild versuchen
    loadImageFallback();
  });

  // -----------------------------------
  // BILDFALLBACK
  // -----------------------------------
  function loadImageFallback() {
    const imgSrc = "data/self/latest_image.png?ts=" + Date.now();
    img.src = imgSrc;

    img.onload = () => {
      mode = "image";
      img.style.display = "block";
      video.style.display = "none";
      placeholder.style.display = "none";

      metaEl.textContent = "Medium: Bild";
      statusEl.textContent = "Status: Bild aktiv";

      window.dispatchEvent(
        new CustomEvent("mira-media-ready", { detail: { mediaType: "image" } })
      );
    };

    img.onerror = () => {
      // Weder Video noch Bild → Platzhalter
      mode = "placeholder";
      img.style.display = "none";
      video.style.display = "none";
      placeholder.style.display = "block";

      metaEl.textContent = "Medium: keines";
      statusEl.textContent = "Status: Platzhalter";

      window.dispatchEvent(
        new CustomEvent("mira-media-ready", { detail: { mediaType: "placeholder" } })
      );
    };
  }
}
