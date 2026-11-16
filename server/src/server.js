import path from "node:path";
import { fileURLToPath } from "node:url";
import { createApp } from "./app.js";
import { createLLM } from "./llm.js";
import { loadPersona } from "./persona.js";
import { createVision } from "./vision.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const persona = loadPersona(process.env.DATA_DIR || path.join(root, "data"));
const llm = createLLM();
const vision = createVision();

const app = createApp({ persona, llm, vision, staticDir: process.env.STATIC_DIR || path.join(root, "public") });
const port = Number(process.env.PORT) || 8080;

app.listen(port, () => {
  console.log(`Doppelganger of ${persona.name} listening on :${port}`);
  console.log(`  persona: ${persona.isSample ? "SAMPLE data (run the ETL to use your own)" : "your data"}, ${persona.examples.length} examples`);
  console.log(`  llm: ${llm.mode}${llm.model ? ` (${llm.model})` : ""}, vision: ${vision.enabled ? "Cloud Vision" : "off"}`);
});
