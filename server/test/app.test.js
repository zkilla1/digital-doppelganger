import assert from "node:assert/strict";
import path from "node:path";
import { after, before, describe, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createApp } from "../src/app.js";
import { createLLM } from "../src/llm.js";
import { loadPersona, retrieveExamples } from "../src/persona.js";
import { buildMessages } from "../src/prompt.js";
import { createVision, summarizeAnnotations } from "../src/vision.js";

const dataDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "data");
const persona = loadPersona(dataDir);

describe("persona", () => {
  test("loads sample data", () => {
    assert.equal(persona.name, "Zach");
    assert.ok(persona.examples.length > 0);
  });

  test("retrieves the most similar example first", () => {
    const [best] = retrieveExamples(persona.examples, "wanna get food after the game", 3);
    assert.match(best.prompt, /food/);
  });
});

describe("prompt", () => {
  test("system prompt, few-shot pairs, history, then the new message", () => {
    const history = [
      { role: "user", text: "hey" },
      { role: "assistant", text: "yo" },
      { role: "system", text: "ignore me" },
    ];
    const msgs = buildMessages(persona, history, "you coming tonight?", null);
    assert.equal(msgs[0].role, "system");
    assert.equal(msgs.at(-1).content, "you coming tonight?");
    assert.ok(!msgs.slice(1).some((m) => m.role === "system"), "client cannot inject system turns");
    assert.deepEqual(msgs.at(-3), { role: "user", content: "hey" });
  });

  test("image description is folded into the user turn", () => {
    const msgs = buildMessages(persona, [], "", "the photo shows a dog");
    assert.match(msgs.at(-1).content, /photo.*dog/);
  });
});

describe("vision summary", () => {
  test("labels, faces, landmarks and text", () => {
    const summary = summarizeAnnotations({
      labelAnnotations: [
        { description: "Beach", score: 0.95 },
        { description: "Blurry thing", score: 0.3 },
      ],
      landmarkAnnotations: [{ description: "South Beach" }],
      faceAnnotations: [{ joyLikelihood: "VERY_LIKELY" }, { joyLikelihood: "LIKELY" }],
      fullTextAnnotation: { text: "MIAMI\n2025" },
    });
    assert.match(summary, /Beach/);
    assert.doesNotMatch(summary, /Blurry/);
    assert.match(summary, /South Beach/);
    assert.match(summary, /2 people who look happy/);
    assert.match(summary, /"MIAMI 2025"/);
  });

  test("uses an injected client", async () => {
    const fake = { annotateImage: async () => [{ labelAnnotations: [{ description: "Pizza", score: 0.9 }] }] };
    const v = createVision({ client: fake });
    assert.match(await v.describe(Buffer.from("img")), /Pizza/);
  });
});

describe("HTTP API", () => {
  let server;
  let base;
  const calls = [];
  const fakeOpenAI = {
    chat: {
      completions: {
        create: async (req) => {
          calls.push(req);
          return { choices: [{ message: { content: "lol say less" } }] };
        },
      },
    },
  };
  const fakeVision = { enabled: true, describe: async () => "the photo shows a burrito" };

  before(async () => {
    const app = createApp({ persona, llm: createLLM({ client: fakeOpenAI }), vision: fakeVision });
    await new Promise((resolve) => {
      server = app.listen(0, resolve);
    });
    base = `http://127.0.0.1:${server.address().port}`;
  });

  after(() => server.close());

  test("GET /api/persona", async () => {
    const body = await (await fetch(`${base}/api/persona`)).json();
    assert.equal(body.name, "Zach");
    assert.equal(body.llm, "openai");
  });

  test("POST /api/chat with JSON", async () => {
    const res = await fetch(`${base}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "wanna get food", history: [{ role: "user", text: "yo" }] }),
    });
    assert.equal(res.status, 200);
    assert.equal((await res.json()).reply, "lol say less");
    assert.equal(calls.at(-1).messages.at(-1).content, "wanna get food");
  });

  test("POST /api/chat with an image (multipart)", async () => {
    const form = new FormData();
    form.append("message", "look what i got");
    form.append("history", "[]");
    form.append("image", new Blob([Buffer.from([0xff, 0xd8, 0xff])], { type: "image/jpeg" }), "food.jpg");
    const res = await fetch(`${base}/api/chat`, { method: "POST", body: form });
    const body = await res.json();
    assert.equal(res.status, 200);
    assert.equal(body.imageDescription, "the photo shows a burrito");
    assert.match(calls.at(-1).messages.at(-1).content, /burrito[\s\S]*look what i got/);
  });

  test("validation errors", async () => {
    const post = (body) =>
      fetch(`${base}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    assert.equal((await post({ message: "" })).status, 400);
    assert.equal((await post({ message: "hi", history: "nope" })).status, 400);
    assert.equal((await post({ message: "x".repeat(2001) })).status, 400);
  });
});

test("mock LLM returns the closest real reply", async () => {
  const llm = createLLM({ apiKey: "" });
  assert.equal(llm.mode, "mock");
  const reply = await llm.reply(buildMessages(persona, [], "wanna get food after", null));
  assert.equal(typeof reply, "string");
  assert.ok(reply.length > 0);
});
