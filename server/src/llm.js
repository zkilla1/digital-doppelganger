import OpenAI from "openai";

/**
 * GPT chat client. Without OPENAI_API_KEY it runs in mock mode and echoes the closest real example,
 * so the UI and pipeline work end to end with no credentials.
 */
export function createLLM({ client, apiKey = process.env.OPENAI_API_KEY, model = process.env.OPENAI_MODEL || "gpt-4o-mini" } = {}) {
  if (!client && !apiKey) {
    return {
      mode: "mock",
      async reply(messages) {
        // Few-shot examples come first, best match first, so this is the closest real reply.
        const examples = messages.filter((m) => m.role === "assistant");
        return examples.length ? examples[0].content : "lol idk";
      },
    };
  }

  const openai = client ?? new OpenAI({ apiKey });
  return {
    mode: "openai",
    model,
    async reply(messages) {
      const completion = await openai.chat.completions.create({
        model,
        messages,
        temperature: 0.9,
        max_tokens: 200,
      });
      return completion.choices[0]?.message?.content?.trim() || "...";
    },
  };
}
