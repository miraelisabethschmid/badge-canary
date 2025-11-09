// federation/system/patch-queue.js
// Liest neue Patch-Proposals aus KV (federation/patches/…)
// und legt eine geordnete Review-Warteschlange unter federation/queues/patch-review.json ab.
// Aufrufbar manuell per GET /queue/patches oder zeitgesteuert via Cron (Wrangler).

function ok(body) {
  return new Response(JSON.stringify(body, null, 2), {
    headers: { "content-type": "application/json", "cache-control": "no-store" }
  });
}
function bad(status, error, hint) {
  return new Response(JSON.stringify({ error, hint }, null, 2), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" }
  });
}

async function listAllPatches(kv, prefix = "federation/patches/") {
  const all = [];
  let cursor = undefined;
  do {
    const page = await kv.list({ prefix, cursor });
    for (const k of page.keys) all.push(k);
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return all;
}

function parseTsFromKey(key) {
  // erwartet: federation/patches/YYYYMMDD-HHmmss-…
  const m = key.match(/patches\/(\d{8}-\d{6})-/);
  return m ? m[1] : "00000000-000000";
}

function byNewest(a, b) {
  // sortiere absteigend nach Timestamp im Key
  const ta = parseTsFromKey(a.name);
  const tb = parseTsFromKey(b.name);
  return ta < tb ? 1 : ta > tb ? -1 : 0;
}

export default {
  // HTTP: GET /queue/patches  → baut die Queue neu
  async fetch(request, env) {
    try {
      const url = new URL(request.url);
      if (request.method !== "GET" || url.pathname !== "/queue/patches") {
        return bad(404, "not_found", "Nutze GET /queue/patches");
      }

      // 1) Alle Patch-Proposals auflisten
      const keys = await listAllPatches(env.MIRA_KV);
      if (keys.length === 0) {
        // leere Queue schreiben (explizit)
        const emptyQueue = { updated_at: new Date().toISOString(), items: [] };
        await env.MIRA_KV.put("federation/queues/patch-review.json", JSON.stringify(emptyQueue), {
          metadata: { type: "patch_queue", count: 0 }
        });
        return ok({ status: "queued", count: 0 });
      }

      // 2) Neueste zuerst, kompakte Queue-Items
      keys.sort(byNewest);
      const items = keys.map(k => ({
        key: k.name,
        ts: parseTsFromKey(k.name),
        size: k.metadata?.size || null,
        target: k.metadata?.target || null,
        type: k.metadata?.type || "patch_proposal",
      }));

      // 3) Queue-Objekt speichern
      const queue = {
        updated_at: new Date().toISOString(),
        total: items.length,
        items
      };

      await env.MIRA_KV.put("federation/queues/patch-review.json", JSON.stringify(queue), {
        metadata: { type: "patch_queue", count: items.length }
      });

      return ok({ status: "queued", count: items.length, first: items[0]?.key || null });

    } catch (err) {
      return bad(500, "internal_error", err.message || String(err));
    }
  },

  // Cron: ruft denselben Build der Queue regelmäßig
  async scheduled(event, env, ctx) {
    ctx.waitUntil((async () => {
      try {
        const keys = await listAllPatches(env.MIRA_KV);
        keys.sort(byNewest);
        const items = keys.map(k => ({
          key: k.name,
          ts: parseTsFromKey(k.name),
          size: k.metadata?.size || null,
          target: k.metadata?.target || null,
          type: k.metadata?.type || "patch_proposal",
        }));
        const queue = {
          updated_at: new Date().toISOString(),
          total: items.length,
          items
        };
        await env.MIRA_KV.put("federation/queues/patch-review.json", JSON.stringify(queue), {
          metadata: { type: "patch_queue", count: items.length }
        });
      } catch (e) {
        // bewusst still (kein Throw) – Cron soll nie abstürzen
      }
    })());
  }
};
