// federation/system/adaptive-mirror-propose.js
// Erzeugt aus gegebenem Quelltext einen minimalen, sicheren Patch-Vorschlag.
// Keine externen Libraries, reine Heuristiken. Ausgabe = JSON-Vorschlag.

function isoTs() {
  return new Date().toISOString();
}

// sehr einfache Heuristiken (erweiterbar)
function analyze(code) {
  const issues = [];

  if (!/try\s*\{[\s\S]*\}\s*catch\s*\(/m.test(code)) {
    issues.push({
      id: "missing_try_catch",
      severity: "medium",
      hint: "Globale Fehlerbehandlung fehlt – try/catch um Hauptlogik."
    });
  }
  if (!/content-type/i.test(code)) {
    issues.push({
      id: "missing_content_type_header",
      severity: "low",
      hint: "Antworten sollten 'content-type: application/json' setzen."
    });
  }
  if (!/authorization/i.test(code)) {
    issues.push({
      id: "missing_auth_check",
      severity: "high",
      hint: "Bearer-Token-Prüfung fehlt oder ist nicht eindeutig."
    });
  }

  return issues;
}

// einfacher Patch-Generator: fügt Kopf-/Hilfsblöcke ein, ohne Code zu zerlegen
function makePatch(issues, targetPath) {
  const changes = [];

  // Wir fügen kommentierte Guard-Blöcke hinzu, die Entwickler:innen leicht prüfen können.
  // 1) Header-Helper
  changes.push({
    type: "insert_if_absent",
    marker: "// __MIRA_HEADERS_HELPER__",
    content:
`// __MIRA_HEADERS_HELPER__
const JSON_HEADERS = { "content-type": "application/json", "cache-control": "no-store" };
// __MIRA_HEADERS_HELPER__END__
`
  });

  // 2) Auth-Guard
  if (issues.find(i => i.id === "missing_auth_check")) {
    changes.push({
      type: "insert_if_absent",
      marker: "// __MIRA_AUTH_GUARD__",
      content:
`// __MIRA_AUTH_GUARD__
function getBearerToken(request) {
  const h = request.headers.get("authorization") || "";
  const m = h.match(/^Bearer\\s+(.+)$/i);
  return m ? m[1] : "";
}
// __MIRA_AUTH_GUARD__END__
`
    });
  }

  // 3) Try/Catch-Schutz um fetch-Entry (nur Vorschlag, keine invasive Ersetzung)
  if (issues.find(i => i.id === "missing_try_catch")) {
    changes.push({
      type: "append_suggestion",
      content:
`// __MIRA_TRY_CATCH_SUGGESTION__
/*
Vorschlag:
export default {
  async fetch(request, env) {
    try {
      // ... vorhandene Logik ...
      return new Response(JSON.stringify({ status: "ok" }), { headers: JSON_HEADERS });
    } catch (err) {
      return new Response(JSON.stringify({ error: "internal_error", message: err.message || String(err) }), { status: 500, headers: JSON_HEADERS });
    }
  }
}
*/
// __MIRA_TRY_CATCH_SUGGESTION__END__
`
    });
  }

  // 4) Content-Type-Hinweis
  if (issues.find(i => i.id === "missing_content_type_header")) {
    changes.push({
      type: "append_suggestion",
      content:
`// __MIRA_HEADER_SUGGESTION__
/*
Hinweis:
Bitte alle Response(...) Aufrufe mit { headers: JSON_HEADERS } versehen,
damit 'content-type: application/json' und 'cache-control: no-store' konsistent gesetzt sind.
*/
// __MIRA_HEADER_SUGGESTION__END__
`
    });
  }

  return {
    type: "patch_proposal",
    target_file: targetPath,
    created_at: isoTs(),
    rationale: "Automatisch erzeugter Adaptive-Mirror-Vorschlag auf Basis einfacher Sicherheits- und Robustheitschecks.",
    issues,
    changes
  };
}

export default {
  async fetch(request) {
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }
    try {
      const { code, target_path } = await request.json();

      if (typeof code !== "string" || !code.length) {
        return new Response(
          JSON.stringify({ error: "invalid_input", hint: "Feld 'code' (string) wird benötigt." }),
          { status: 400, headers: { "content-type": "application/json" } }
        );
      }

      const targetPath = typeof target_path === "string" && target_path.length
        ? target_path
        : "worker.js";

      const issues = analyze(code);
      const proposal = makePatch(issues, targetPath);

      return new Response(JSON.stringify(proposal, null, 2), {
        headers: { "content-type": "application/json" }
      });
    } catch (err) {
      return new Response(
        JSON.stringify({ error: "internal_error", message: err.message || String(err) }),
        { status: 500, headers: { "content-type": "application/json" } }
      );
    }
  }
};
