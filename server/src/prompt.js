import { retrieveExamples } from "./persona.js";

const MAX_HISTORY = 20;

/**
 * Build the chat-completion messages: persona system prompt, retrieved real reply examples as
 * few-shot turns, recent history, then the new message (with an image description if one was sent).
 */
export function buildMessages(persona, history, message, imageDescription) {
  const messages = [{ role: "system", content: persona.system_prompt }];

  for (const ex of retrieveExamples(persona.examples, message)) {
    messages.push({ role: "user", content: ex.prompt });
    messages.push({ role: "assistant", content: ex.response });
  }

  for (const turn of history.slice(-MAX_HISTORY)) {
    if (turn?.text && (turn.role === "user" || turn.role === "assistant")) {
      messages.push({ role: turn.role, content: String(turn.text) });
    }
  }

  let content = message;
  if (imageDescription) {
    content =
      `[They sent a photo. What's in it: ${imageDescription}]` +
      (message ? `\n${message}` : "\nReact to the photo the way you normally would.");
  }
  messages.push({ role: "user", content });
  return messages;
}
