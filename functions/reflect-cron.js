// /functions/reflect-cron.js
export async function onRequestGet(context) {
  const { request, env } = context;
  const JSON_HEADERS = {
    "content-type": "application/json",
    "cache-control": "no-store"
  };

  const authHeader = request.headers.get("authorization") || "";
  const m = authHeader.match(/^Bearer\s+(.+)$/i);
  const token = m ? m[1] : "";
  if (env.DISPATCH_TOKEN && token !== env.DISPATCH_TOKEN) {
    return new Response(
      JSON.stringify({ error: "forbidden", hint: "invalid or missing Bearer token" }),
      { status: 403, headers: JSON_HEADERS }
    );
  }

  const body = { status: "ok", endpoint: "/reflect", mode: "ready",
                 note: "Platzhalter ist angelegt und funktionsbereit." };
  return new Response(JSON.stringify(body), { status: 200, headers: JSON_HEADERS });
}

export async function onRequestPost() {
  return new Response(
    JSON.stringify({ error: "method_not_allowed", must: "GET /reflect" }),
    { status: 405, headers: { "content-type": "application/json", "cache-control": "no-store" } }
  );
}
