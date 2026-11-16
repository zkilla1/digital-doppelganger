import fs from "node:fs";
import path from "node:path";
import express from "express";
import multer from "multer";
import { buildMessages } from "./prompt.js";

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

export function createApp({ persona, llm, vision, staticDir }) {
  const app = express();
  const upload = multer({
    storage: multer.memoryStorage(),
    limits: { fileSize: MAX_IMAGE_BYTES },
    fileFilter: (_req, file, cb) => cb(null, file.mimetype.startsWith("image/")),
  });

  app.use(express.json({ limit: "1mb" }));

  app.get("/health", (_req, res) => res.json({ status: "ok" }));

  app.get("/api/persona", (_req, res) => {
    res.json({
      name: persona.name,
      rules: persona.rules,
      exampleCount: persona.examples.length,
      isSample: persona.isSample,
      llm: llm.mode,
      vision: vision.enabled,
    });
  });

  app.post("/api/chat", upload.single("image"), async (req, res, next) => {
    try {
      const message = String(req.body.message ?? "").trim();
      if (!message && !req.file) return res.status(400).json({ error: "send a message or an image" });
      if (message.length > 2000) return res.status(400).json({ error: "message too long" });

      let history = [];
      if (req.body.history) {
        try {
          history = typeof req.body.history === "string" ? JSON.parse(req.body.history) : req.body.history;
        } catch {
          return res.status(400).json({ error: "history must be JSON" });
        }
        if (!Array.isArray(history)) return res.status(400).json({ error: "history must be an array" });
      }

      const imageDescription = req.file ? await vision.describe(req.file.buffer) : null;
      const messages = buildMessages(persona, history, message, imageDescription);
      const reply = await llm.reply(messages);
      res.json({ reply, imageDescription });
    } catch (err) {
      next(err);
    }
  });

  if (staticDir && fs.existsSync(staticDir)) {
    app.use(express.static(staticDir));
    app.get(/^(?!\/api\/).*/, (_req, res) => res.sendFile(path.join(staticDir, "index.html")));
  }

  app.use((err, _req, res, _next) => {
    console.error(err);
    const status = err.code === "LIMIT_FILE_SIZE" ? 413 : 500;
    res.status(status).json({ error: status === 413 ? "image too large (8 MB max)" : "something went wrong" });
  });

  return app;
}
