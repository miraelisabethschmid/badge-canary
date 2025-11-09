// federation/system/patch-saver.js
// Speichert einen Patch-Vorschlag (JSON) deterministisch in KV unter federation/patches/…
// Keine Tests, keine Auto-Merges. Nur sichere Ablage.

function isoTs() {
  // YYYYMMDD-HHmmss
  const s = new Date().toISOString().substring(0,19).replace(/[:]/g,"-").replace("T","-");
  return s;
}

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

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return bad(405, "method_not_allowed", "Bitte per POST senden.");
    }

    try {
      // Erwartet den JSON-Patch-Vorschlag aus Schritt 4 (adaptive-mirror-propose.js)
      const proposal = await request.json();

      // Minimalprüfung
      if (!proposal || proposal.type !== "patch_proposal") {
        return bad(400, "invalid_proposal", "Feld 'type' muss 'patch_proposal' sein.");
      }
      if (!proposal.target_file || typeof proposal.target_file !== "string") {
        return bad(400, "invalid_target_file", "Feld 'target_file' (string) fehlt.");
      }
      if (!Array.isArray(proposal.changes) || proposal.changes.length === 0) {
        return bad(400, "empty_changes", "Liste 'changes' ist leer.");
      }

      // Key deterministisch: federation/patches/<YYYYMMDD-HHmmss>-<safeTarget>.json
      const ts = isoTs();
      const safeTarget = proposal.target_file.replace(/[^a-zA-Z0-9._/-]+/g, "_");
      const key = `federation/patches/${ts}-${safeTarget}.json`;

      // Metadaten ergänzen
      const enriched = {
        ...proposal,
        saved_at: new Date().toISOString(),
        storage_key: key,
        version: "alpha-1"
      };

      // Speichern in KV (Namespace muss bereits gebunden sein: env.MIRA_KV)
      await env.MIRA_KV.put(key, JSON.stringify(enriched), {
        metadata: { type: "patch_proposal", target: proposal.target_file }
      });

      return ok({ status: "stored", key, bytes: JSON.stringify(enriched).length });

    } catch (err) {
      return bad(500, "internal_error", err.message || String(err));
    }
  }
};
