// federation/bridge/evaluate-endpoint.js
// Minimaler HTTP-Endpoint, der den Resonanz-Evaluator nutzt.
// Erwartet POST mit JSON: { "responses": [ ... ] }
// Antwort: JSON mit resonance_index, policy, report_md
import { evaluateResonance } from "../metrics/resonance-evaluator.js";

const JSON_HEADERS = { "content-type": "application/json", "cache-control": "no-store" };

export default {
  /**
   * handle(request, env): wird von deinem Haupt-Worker aufgerufen,
   * wenn die Route /federation/evaluate getroffen wird.
   */
  async handle(request, env) {
    try {
      if (request.method !== "POST") {
        return new Response(JSON.stringify({ error: "method_not_allowed" }), { status: 405, headers: JSON_HEADERS });
      }

      const ct = request.headers.get("content-type") || "";
      if (!ct.includes("application/json")) {
        return new Response(JSON.stringify({ error: "unsupported_media_type", must: "application/json" }), { status: 415, headers: JSON_HEADERS });
      }

      const body = await request.json();
      const arr = Array.isArray(body?.responses) ? body.responses : [];
      const result = evaluateResonance(arr);

      // Optional: in KV protokollieren, wenn vorhanden (nicht erforderlich)
      // Key: federation:reports:<ISO-Timestamp>
      if (env && env.MIRA_KV) {
        const ts = new Date().toISOString().replace(/[:]/g, "-");
        const key = `federation:reports:${ts}`;
        const payload = {
          created_at: ts,
          resonance_index: result.resonance_index,
          policy: result.policy,
          metrics: result.metrics,
          per_source: result.per_source
        };
        // Fehler hier nicht fatal machen:
        try { await env.MIRA_KV.put(key, JSON.stringify(payload), { metadata: { type: "resonance_report" } }); } catch (_) {}
      }

      return new Response(JSON.stringify(result), { status: 200, headers: JSON_HEADERS });
    } catch (err) {
      return new Response(JSON.stringify({ error: "internal_error", message: err?.message || String(err) }), { status: 500, headers: JSON_HEADERS });
    }
  }
};
