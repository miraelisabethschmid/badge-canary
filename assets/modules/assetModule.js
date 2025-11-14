// assetModule.js
// Verantwortlich für: Video → Bild → Fallback

export async function loadMedia(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = ""; // zuerst leeren

  // 1) VIDEO versuchen
  const videoUrl = "data/self/latest_video.mp4";
  const video = document.createElement("video");
  video.src = videoUrl + "?v=" + Date.now();
  video.preload = "metadata";
  video.playsInline = true;
  video.muted = true;
  video.autoplay = false;
  video.style.width = "100%";
  video.style.borderRadius = "12px";

  // Wenn Video lädt:
  video.oncanplay = () => {
    container.innerHTML = "";
    container.appendChild(video);
  };

  // Wenn Video fehlschlägt → Bild laden
  video.onerror = () => {
    loadImage(container);
  };

  // HEAD prüfen, ob Video existiert
  try {
    const res = await fetch(videoUrl, { method: "HEAD" });
    if (res.ok) {
      container.appendChild(video);
      return;
    }
  } catch (_) {}

  // Falls HEAD fehlschlägt → direkt Bild
  loadImage(container);
}

async function loadImage(container) {
  container.innerHTML = "";

  const imgUrl = "data/self/latest_image.png";
  const img = new Image();
  img.src = imgUrl + "?v=" + Date.now();
  img.style.width = "100%";
  img.style.borderRadius = "12px";

  img.onload = () => {
    container.innerHTML = "";
    container.appendChild(img);
  };

  img.onerror = () => {
    loadFallback(container);
  };
}

function loadFallback(container) {
  container.innerHTML = `
    <div style="
      padding: 30px;
      text-align: center;
      color: #888;
      font-style: italic;
      background: #111;
      border-radius: 12px;">
      Kein Bild oder Video vorhanden.
    </div>
  `;
}
