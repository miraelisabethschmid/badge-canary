/* Mira Auto-Sync — nie leer, immer live */
const STATE = {
  manifestUrl: (function(){
    // funktioniert bei Root-Hosting und /docs
    const base = location.pathname.endsWith('/') ? location.pathname : location.pathname.replace(/[^/]+$/, '');
    return (base.includes('/docs/') ? 'data/manifest.json' : 'docs/data/manifest.json');
  })(),
  pollingMs: 60000,
  lastUpdated: null,
};

const Inline = {
  placeholderSVG:
    'data:image/svg+xml;utf8,' + encodeURIComponent(`<?xml version="1.0" encoding="UTF-8"?>\
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800">\
  <defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1">\
    <stop offset="0%" stop-color="#11182b"/><stop offset="100%" stop-color="#1a2340"/></linearGradient></defs>\
  <rect width="100%" height="100%" fill="url(#g)"/>\
  <g fill="#e9ecf5" font-family="system-ui,Segoe UI,Roboto" text-anchor="middle">\
    <text x="50%" y="45%" font-size="42">Mira — Platzhalterbild</text>\
    <text x="50%" y="55%" font-size="20">Kein Bild vorhanden</text>\
  </g>\
</svg>`),
  silentWav: 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAgD4AAIA+AAABAAgAZGF0YQAAAAA=' // 0s still
};

async function fetchManifest() {
  try {
    const res = await fetch(STATE.manifestUrl + '?t=' + Date.now(), { cache: 'no-store' });
    if (!res.ok) throw new Error('manifest fetch failed');
    const m = await res.json();
    return m;
  } catch {
    // Fallback-Manifest
    return {
      updated: new Date().toISOString(),
      image: { candidates: ['docs/data/self/latest_image.svg'] },
      audio: { candidates: ['docs/data/voice/audio/latest.wav'] }
    };
  }
}

async function firstAvailable(cands) {
  for (const u of (cands || [])) {
    try {
      const r = await fetch(u + '?t=' + Date.now(), { method: 'HEAD', cache: 'no-store' });
      if (r.ok) return u;
    } catch {}
  }
  return null;
}

function preloadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(url);
    img.onerror = reject;
    img.src = url + (url.includes('?') ? '&' : '?') + 't=' + Date.now();
  });
}

async function loadImage(cands) {
  const el = document.getElementById('portrait');
  const status = document.getElementById('imgStatus');
  status.textContent = 'Suche Bild…';
  const url = await firstAvailable(cands);
  if (url) {
    try {
      await preloadImage(url);
      el.src = url + '?t=' + Date.now();
      status.textContent = 'Bild geladen';
      return;
    } catch {}
  }
  el.src = Inline.placeholderSVG;
  status.textContent = 'Platzhalter aktiv';
}

async function loadAudio(cands) {
  const el = document.getElementById('voice');
  const status = document.getElementById('audStatus');
  const url = await firstAvailable(cands);
  if (url) {
    el.src = url + '?t=' + Date.now();
    status.textContent = 'Audio bereit';
  } else {
    el.src = Inline.silentWav;
    status.textContent = 'Stiller Fallback';
  }
}

async function applyManifest(m) {
  document.getElementById('liveTs').textContent = 'Live · ' + new Date().toISOString();
  await loadImage(m.image && m.image.candidates);
  await loadAudio(m.audio && m.audio.candidates);
  STATE.lastUpdated = m.updated;
}

async function poll() {
  try {
    const m = await fetchManifest();
    if (STATE.lastUpdated !== m.updated) {
      await applyManifest(m);
    }
  } catch {}
  setTimeout(poll, STATE.pollingMs);
}

async function tryAutoplay() {
  const el = document.getElementById('voice');
  const status = document.getElementById('audStatus');
  try {
    await el.play();
    sessionStorage.setItem('audioUnlocked', '1');
    status.textContent = 'Spielt';
  } catch {
    status.textContent = 'Autoplay-Schutz – ▶ tippen';
  }
}

function wireControls() {
  const play = document.getElementById('btnPlay');
  const pause = document.getElementById('btnPause');
  play.onclick = tryAutoplay;
  pause.onclick = () => document.getElementById('voice').pause();
  if (sessionStorage.getItem('audioUnlocked') === '1') tryAutoplay();
  document.addEventListener('touchstart', tryAutoplay, { once:true, passive:true });
  document.addEventListener('click', tryAutoplay, { once:true });
}

export async function miraInit() {
  wireControls();
  const m = await fetchManifest();
  await applyManifest(m);
  poll();
}
