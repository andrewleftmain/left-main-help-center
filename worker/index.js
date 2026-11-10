/**
 * Left Main Help Center - "Ask" chatbot backend.
 *
 * Fetches corpus.txt (every article, pre-stitched into plain text by
 * build.py on each deploy) from the live site, caches it for
 * CORPUS_TTL_SECONDS, and answers questions with OpenAI's Chat Completions
 * API using that corpus as context - no embeddings/vector DB, the whole
 * site is small enough to hand over directly.
 */

const CORPUS_TTL_SECONDS = 60 * 30; // 30 minutes
const ALLOWED_ORIGINS = [
  "https://andrewleftmain.github.io",
  "http://localhost:8731",
  "http://127.0.0.1:8731",
];
const OPENAI_MODEL = "gpt-4o-mini";
const MAX_HISTORY_TURNS = 6;

function corsHeaders(origin) {
  const allowed = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };
}

const SITE_BASE = "https://andrewleftmain.github.io/left-main-help-center";

async function fetchCorpus(env) {
  // build.py writes this as one pre-stitched plain-text file alongside the
  // site on every deploy - a single fetch, well under Cloudflare's free-tier
  // subrequest-per-invocation limit (fetching all ~126 articles individually
  // blew past it).
  const res = await fetch(`${SITE_BASE}/corpus.txt?_=${Date.now()}`);
  if (!res.ok) throw new Error("Could not load corpus.txt");
  return res.text();
}

async function getCorpus(env, ctx) {
  const cache = caches.default;
  const cacheKey = new Request("https://help-bot-corpus.internal/corpus");
  const cached = await cache.match(cacheKey);
  if (cached) return cached.text();

  const corpus = await fetchCorpus(env);
  const response = new Response(corpus, {
    headers: { "Cache-Control": `max-age=${CORPUS_TTL_SECONDS}`, "Content-Type": "text/plain" },
  });
  ctx.waitUntil(cache.put(cacheKey, response.clone()));
  return corpus;
}

const SYSTEM_PROMPT = `You are the help assistant for Left Main REI's customer help center.
Answer ONLY using the help center content provided below - do not use outside knowledge about Salesforce or guess at behavior that isn't described.
If the answer isn't in the content, say you don't see that covered and suggest the user check the full help center or contact support - don't make something up.
Keep answers concise and practical. When it's useful, mention which article the answer comes from and include its URL as a markdown link.

HELP CENTER CONTENT:
`;

async function handleChat(request, env, ctx) {
  let payload;
  try {
    payload = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), { status: 400 });
  }
  const message = (payload.message || "").toString().slice(0, 2000);
  const history = Array.isArray(payload.history) ? payload.history.slice(-MAX_HISTORY_TURNS * 2) : [];
  if (!message.trim()) {
    return new Response(JSON.stringify({ error: "message is required" }), { status: 400 });
  }

  let corpus;
  try {
    corpus = await getCorpus(env, ctx);
  } catch (e) {
    return new Response(JSON.stringify({ error: "Could not load help center content: " + e.message }), { status: 502 });
  }

  const messages = [
    { role: "system", content: SYSTEM_PROMPT + corpus },
    ...history.filter((m) => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string"),
    { role: "user", content: message },
  ];

  const openaiRes = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${env.OPENAI_API_KEY}`,
    },
    body: JSON.stringify({
      model: OPENAI_MODEL,
      messages,
      temperature: 0.2,
      max_tokens: 700,
    }),
  });

  if (!openaiRes.ok) {
    const errText = await openaiRes.text().catch(() => "");
    return new Response(JSON.stringify({ error: "OpenAI API error: " + errText.slice(0, 500) }), { status: 502 });
  }
  const data = await openaiRes.json();
  const answer = data.choices?.[0]?.message?.content || "Sorry, I couldn't generate an answer.";
  return new Response(JSON.stringify({ answer }), { headers: { "Content-Type": "application/json" } });
}

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    const headers = corsHeaders(origin);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers });
    }
    if (request.method !== "POST") {
      return new Response(JSON.stringify({ error: "POST only" }), { status: 405, headers });
    }

    try {
      const res = await handleChat(request, env, ctx);
      const body = await res.text();
      return new Response(body, {
        status: res.status,
        headers: { ...headers, "Content-Type": "application/json" },
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: e.message || "Unknown error" }), { status: 500, headers });
    }
  },
};
