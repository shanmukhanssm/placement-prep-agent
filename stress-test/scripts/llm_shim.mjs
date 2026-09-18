// llm_shim.mjs — minimal OpenAI-compatible /chat/completions server backed by z-ai-web-dev-sdk.
// Purpose: run placement-prep-agent tests when the requested Zen free-tier model is API-gated.
// - Converts OpenAI messages → z-ai messages (system → 'assistant' role per skill docs).
// - If the request carries `tools` (the repo binds exactly one pydantic schema), injects an
//   OUTPUT CONTRACT system line with the JSON schema, then wraps the model's JSON reply into
//   a synthetic OpenAI tool_calls entry so langchain's parser sees a normal tool call.
// - Retries the SDK call twice on error. Logs every call to stdout (shim.log).
// Run: cd /home/z/.bun/install/global && bun /home/z/my-project/scripts/llm_shim.mjs
import http from "http";
import ZAI from "/home/z/.bun/install/global/node_modules/z-ai-web-dev-sdk/dist/index.js";

const PORT = 8099;
const MODEL_LABEL = process.env.SHIM_MODEL_LABEL || "shim-llm";

let zai = null;
async function getZAI() {
  if (!zai) zai = await ZAI.create();
  return zai;
}

function extractJSON(text) {
  if (!text) return null;
  const t = String(text).trim();
  try { return JSON.parse(t); } catch {}
  const s = t.indexOf("{"), e = t.lastIndexOf("}");
  if (s !== -1 && e > s) {
    try { return JSON.parse(t.slice(s, e + 1)); } catch {}
  }
  return null;
}

function schemaContract(tools) {
  if (!Array.isArray(tools) || tools.length === 0) return null;
  const t = tools[0];
  const fn = t.function || t;
  const name = fn.name || "structured_output";
  const schema = fn.parameters || { type: "object" };
  return {
    name,
    instruction:
      `OUTPUT CONTRACT (overrides everything): You are calling the function "${name}". ` +
      `Respond with ONE single JSON object and NOTHING else — no prose, no markdown fences, ` +
      `no keys outside the schema. It must validate against this JSON Schema:\n` +
      JSON.stringify(schema),
  };
}

function toZaiMessages(messages, contract) {
  const out = [];
  for (const m of messages || []) {
    const role = m.role === "system" ? "assistant" : m.role;
    const content = typeof m.content === "string" ? m.content : JSON.stringify(m.content);
    if (role === "user" || role === "assistant") out.push({ role, content });
  }
  if (contract) out.push({ role: "assistant", content: contract.instruction });
  return out;
}

async function handleChat(body) {
  const contract = schemaContract(body.tools);
  const z = await getZAI();
  let lastErr;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const completion = await z.chat.completions.create({
        messages: toZaiMessages(body.messages, contract),
        thinking: { type: "disabled" },
      });
      const raw = completion?.choices?.[0]?.message?.content ?? "";
      const message = { role: "assistant", content: raw };
      if (contract) {
        const obj = extractJSON(raw);
        if (obj !== null) {
          message.tool_calls = [{
            id: "call_shim_" + Date.now(),
            type: "function",
            function: { name: contract.name, arguments: JSON.stringify(obj) },
          }];
        }
        // no valid JSON → plain content; the repo's content-JSON parser handles the retry
      }
      return {
        id: "chatcmpl-shim-" + Date.now(),
        object: "chat.completion",
        created: Math.floor(Date.now() / 1000),
        model: body.model || MODEL_LABEL,
        choices: [{ index: 0, message, finish_reason: "stop" }],
        usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
      };
    } catch (e) {
      lastErr = e;
      await new Promise(r => setTimeout(r, 1200 * attempt));
      zai = null; // rebuild client on next attempt
    }
  }
  throw lastErr;
}

const server = http.createServer((req, res) => {
  const t0 = Date.now();
  let body = "";
  req.on("data", c => (body += c));
  req.on("end", async () => {
    try {
      if (req.method === "GET" && (req.url.includes("/models"))) {
        const out = { object: "list", data: [{ id: MODEL_LABEL, object: "model", owned_by: "shim" }] };
        res.writeHead(200, { "Content-Type": "application/json" });
        return res.end(JSON.stringify(out));
      }
      if (!(req.method === "POST" && req.url.includes("/chat/completions"))) {
        res.writeHead(404, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ error: { message: "not found: " + req.url } }));
      }
      const parsed = body ? JSON.parse(body) : {};
      const out = await handleChat(parsed);
      const hasTools = Array.isArray(parsed.tools) && parsed.tools.length > 0;
      const toolOk = out.choices[0].message.tool_calls ? "TOOL_OK" : "TOOL_MISS";
      console.log(`[shim] ${new Date().toISOString()} tools=${hasTools ? toolOk : "-"} ` +
        `${Date.now() - t0}ms len=${(out.choices[0].message.content || "").length}`);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(out));
    } catch (e) {
      console.error(`[shim] ERROR ${Date.now() - t0}ms ${e?.message || e}`);
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: { message: String(e?.message || e), type: "shim_error" } }));
    }
  });
});

server.listen(PORT, "127.0.0.1", () => console.log(`[shim] listening on http://127.0.0.1:${PORT}/v1`));
