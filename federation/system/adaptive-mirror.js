// federation/system/adaptive-mirror.js
// Node-Blueprint: erzeugt Patch-Vorschläge für worker.js, ohne direkt zu ändern.
// Laufumgebung: GitHub Actions (node >= 18) oder lokal mit `node federation/system/adaptive-mirror.js`

import fs from "node:fs";
import path from "node:path";

const TARGET_FILE = "worker.js"; // Ziel: Cloudflare Worker im Repo-Root
const PATCH_DIR   = "federation/patches";

function ensureDir(p) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
}

function readText(p) {
  return fs.readFileSync(p, "utf8");
}

// sehr schlanke statische Checks (erweiterbar)
function analyze(code) {
  const issues = [];

  if (!/try\s*\{[\s\S]*\}\s*catch\s*\(/m.test(code)) {
    issues.push({
      id: "missing_global_trycatch",
      why: "Globale Fehlerbehandlung fehlt/ist zu schwach.",
      fix: "Wrapper try/catch um fetch-Handler oder zentrale Fehlerantwort.",
      impact: "Stabilität"
    });
  }

  if (!/content-type/i.test(code)) {
    issues.push({
      id: "missing_content_type",
      why: "Kein einheitlicher JSON Content-Type gesetzt.",
      fix: 'Konstante JSON_HEADERS einführen.',
      impact: "Korrektheit"
    });
  }

  if (!/authorization/i.test(code)) {
    issues.push({
      id: "missing_auth_guard",
      why: "Kein Bearer-Token-Guard erkennbar.",
      fix: "Authorization Header prüfen und 403 bei Fehlersituation.",
      impact: "Security"
    });
  }

  return issues;
}

function buildPatch(issues) {
  // Minimaler, generischer Patch-Vorschlag als JSON (kein direkter Code-Diff)
  // Kann von einem Workflow später in echte Code-Diffs übersetzt werden.
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  return {
    type: "adaptive-mirror-proposal",
    timestamp: ts,
    target_file: TARGET_FILE,
    priority: Math.min(1.0,
      issues.reduce((s, it) => s + (it.impact === "Security" ? 0.5 : it.impact === "Stabilität" ? 0.35 : 0.2), 0)
    ),
    issues,
    suggestions: [
      {
        id: "introduce_json_headers",
        description: "Einheitliche JSON_HEADERS nutzen",
        patch_kind: "snippet",
        apply_hint: "am Dateianfang",
        snippet:
`const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store"
};`
      },
      {
        id: "robust_auth_guard",
        description: "Robustan Bearer-Token-Guard via Regex",
        patch_kind: "snippet",
        apply_hint: "im fetch-Handler vor Routenlogik",
        snippet:
`const auth = request.headers.get("authorization") || "";
const m = auth.match(/^Bearer\\s+(.+)$/i);
const token = m ? m[1] : "";
if (!token || token !== env.DISPATCH_TOKEN) {
  return new Response(JSON.stringify({ error: "forbidden" }), { status: 403, headers: JSON_HEADERS });
}`
      },
      {
        id: "global_try_catch",
        description: "Zentraler try/catch um die Routenlogik",
        patch_kind: "guidance",
        apply_hint: "fetch-Handler umschließen",
        snippet: "// try { … } catch (err) { return new Response(JSON.stringify({error:'internal_error'}),{status:500,headers:JSON_HEADERS}); }"
      }
    ]
  };
}

function main() {
  const targetPath = path.resolve(TARGET_FILE);
  if (!fs.existsSync(targetPath)) {
    console.error(`[adaptive-mirror] Datei nicht gefunden: ${TARGET_FILE}`);
    process.exit(1);
  }

  const code = readText(targetPath);
  const issues = analyze(code);

  if (issues.length === 0) {
    console.log(JSON.stringify({ status: "ok", message: "Keine Optimierungsvorschläge." }, null, 2));
    return;
  }

  ensureDir(PATCH_DIR);
  const proposal = buildPatch(issues);
  const out = path.join(PATCH_DIR, `proposal-${proposal.timestamp}.json`);
  fs.writeFileSync(out, JSON.stringify(proposal, null, 2), "utf8");

  console.log(JSON.stringify({ status: "proposal_created", file: out, issues: issues.map(i => i.id) }, null, 2));
}

main();
