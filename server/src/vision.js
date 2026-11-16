import vision from "@google-cloud/vision";

/** Summarize a Cloud Vision annotateImage response as one sentence the LLM can react to. */
export function summarizeAnnotations(result) {
  const parts = [];

  const labels = (result.labelAnnotations ?? []).filter((l) => l.score >= 0.7).map((l) => l.description);
  if (labels.length) parts.push(`shows ${labels.slice(0, 6).join(", ")}`);

  const landmark = result.landmarkAnnotations?.[0]?.description;
  if (landmark) parts.push(`taken at ${landmark}`);

  const faces = result.faceAnnotations ?? [];
  if (faces.length) {
    const likely = (v) => v === "LIKELY" || v === "VERY_LIKELY";
    const moods = new Set();
    for (const f of faces) {
      if (likely(f.joyLikelihood)) moods.add("happy");
      if (likely(f.sorrowLikelihood)) moods.add("sad");
      if (likely(f.angerLikelihood)) moods.add("angry");
      if (likely(f.surpriseLikelihood)) moods.add("surprised");
    }
    const who = faces.length === 1 ? "1 person" : `${faces.length} people`;
    parts.push(moods.size ? `${who} who look ${[...moods].join(" and ")}` : who);
  }

  const text = result.fullTextAnnotation?.text?.trim() ?? result.textAnnotations?.[0]?.description?.trim();
  if (text) parts.push(`text reading "${text.replace(/\s+/g, " ").slice(0, 200)}"`);

  return parts.length ? `the photo ${parts.join("; ")}` : "a photo Cloud Vision couldn't identify";
}

export function createVision({ client } = {}) {
  const enabled = Boolean(client || process.env.GOOGLE_APPLICATION_CREDENTIALS || process.env.K_SERVICE);
  if (!enabled) {
    return { enabled: false, describe: async () => "a photo (image understanding is off; set up Cloud Vision)" };
  }
  const annotator = client ?? new vision.ImageAnnotatorClient();

  return {
    enabled: true,
    async describe(buffer) {
      const [result] = await annotator.annotateImage({
        image: { content: buffer.toString("base64") },
        features: [
          { type: "LABEL_DETECTION", maxResults: 10 },
          { type: "FACE_DETECTION", maxResults: 5 },
          { type: "LANDMARK_DETECTION", maxResults: 1 },
          { type: "TEXT_DETECTION" },
        ],
      });
      if (result.error?.message) throw new Error(`Cloud Vision: ${result.error.message}`);
      return summarizeAnnotations(result);
    },
  };
}
