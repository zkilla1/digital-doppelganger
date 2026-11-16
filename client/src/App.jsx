import { useEffect, useRef, useState } from "react";

export default function App() {
  const [persona, setPersona] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [image, setImage] = useState(null);
  const [typing, setTyping] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef(null);
  const bottom = useRef(null);

  useEffect(() => {
    fetch("/api/persona")
      .then((r) => r.json())
      .then(setPersona)
      .catch(() => setError("Can't reach the server."));
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

  async function send(e) {
    e.preventDefault();
    if (!text.trim() && !image) return;

    const outgoing = { role: "user", text: text.trim(), imageUrl: image && URL.createObjectURL(image) };
    const history = messages.map(({ role, text }) => ({ role, text }));
    setMessages((prev) => [...prev, outgoing]);
    setText("");
    setError("");
    setTyping(true);

    const form = new FormData();
    form.append("message", outgoing.text);
    form.append("history", JSON.stringify(history));
    if (image) form.append("image", image);
    setImage(null);

    try {
      const res = await fetch("/api/chat", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Request failed");
      // Split multi-line replies into separate bubbles, like a real burst of texts.
      const bubbles = data.reply.split("\n").filter(Boolean);
      for (const [i, line] of bubbles.entries()) {
        if (i > 0) await new Promise((r) => setTimeout(r, 450));
        setMessages((prev) => [...prev, { role: "assistant", text: line }]);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setTyping(false);
    }
  }

  const name = persona?.name ?? "…";

  return (
    <div className="phone">
      <header>
        <div className="avatar">{name[0]}</div>
        <div>
          <div className="name">{name}</div>
          <div className="status">
            digital doppelganger
            {persona && ` · ${persona.llm === "mock" ? "mock mode" : "GPT"}${persona.vision ? " · Cloud Vision" : ""}`}
          </div>
        </div>
      </header>

      {persona?.isSample && (
        <div className="banner">Using sample data. Run the ETL on your own messages to train your doppelganger.</div>
      )}

      <div className="thread">
        {messages.length === 0 && <p className="empty">Text {name}'s doppelganger. Send a photo too.</p>}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role === "user" ? "me" : "them"}`}>
            {m.imageUrl && <img src={m.imageUrl} alt="attachment" />}
            {m.text}
          </div>
        ))}
        {typing && (
          <div className="bubble them typing">
            <span />
            <span />
            <span />
          </div>
        )}
        <div ref={bottom} />
      </div>

      {error && <div className="error">{error}</div>}

      <form className="composer" onSubmit={send}>
        <button type="button" className="attach" onClick={() => fileInput.current.click()} aria-label="Attach photo">
          +
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => {
            setImage(e.target.files[0] ?? null);
            e.target.value = "";
          }}
        />
        <div className="input-wrap">
          {image && (
            <div className="preview">
              📷 {image.name}
              <button type="button" onClick={() => setImage(null)} aria-label="Remove photo">
                ×
              </button>
            </div>
          )}
          <input placeholder="Text message" value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} />
        </div>
        <button type="submit" className="send" disabled={typing || (!text.trim() && !image)} aria-label="Send">
          ↑
        </button>
      </form>
    </div>
  );
}
