import fs from "node:fs";
import path from "node:path";

const WORD_RE = /[a-z0-9']+/g;

export function tokenize(text) {
  return new Set(text.toLowerCase().match(WORD_RE) ?? []);
}

/**
 * Load persona.json + examples.jsonl written by the ETL pipeline. Falls back to the
 * *.sample.* files so the app runs before you've processed your own messages.
 */
export function loadPersona(dataDir) {
  const pick = (name, sample) => {
    const real = path.join(dataDir, name);
    return fs.existsSync(real) ? real : path.join(dataDir, sample);
  };
  const personaPath = pick("persona.json", "persona.sample.json");
  const examplesPath = pick("examples.jsonl", "examples.sample.jsonl");

  const persona = JSON.parse(fs.readFileSync(personaPath, "utf8"));
  const examples = fs
    .readFileSync(examplesPath, "utf8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line))
    .map((ex) => ({ ...ex, tokens: tokenize(ex.prompt) }));

  return { ...persona, examples, isSample: personaPath.endsWith(".sample.json") };
}

/** Pick the examples whose prompts overlap most with the incoming message (Jaccard similarity). */
export function retrieveExamples(examples, message, k = 6) {
  const query = tokenize(message);
  if (query.size === 0) return examples.slice(0, k);

  return examples
    .map((ex) => {
      let shared = 0;
      for (const t of query) if (ex.tokens.has(t)) shared++;
      const union = query.size + ex.tokens.size - shared;
      return { ex, score: union ? shared / union : 0 };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map(({ ex }) => ex);
}
