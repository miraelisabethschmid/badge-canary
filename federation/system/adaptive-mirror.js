export default {
  async fetch(request) {
    if (request.method !== "POST") {
      return new Response("Use POST with JSON payload.", { status: 405 });
    }

    try {
      const { code_sample } = await request.json();

      // einfache statische Analyse
      let issues = [];
      if (!code_sample.includes("try")) issues.push("Fehlerbehandlung fehlt");
      if (!code_sample.includes("Response")) issues.push("Response-Aufbau unvollständig");

      const patchProposal = {
        timestamp: new Date().toISOString(),
        found_issues: issues,
        recommendation:
          issues.length === 0
            ? "Code stabil, keine Änderungen empfohlen."
            : "Ergänze try/catch und überprüfe Response-Header.",
      };

      return new Response(JSON.stringify(patchProposal, null, 2), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    } catch (err) {
      return new Response(
        JSON.stringify({ error: "internal_error", message: err.message }),
        { status: 500, headers: { "content-type": "application/json" } }
      );
    }
  },
};
