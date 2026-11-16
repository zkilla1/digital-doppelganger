"""Clean messages, group them into conversations, and build (their message -> my reply) pairs."""

import re
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import groupby

URL_RE = re.compile(r"https?://\S+")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
OBJECT_REPLACEMENT = "￼"  # placeholder iMessage leaves where an attachment was

DEFAULT_GAP = timedelta(minutes=30)


@dataclass
class Turn:
    is_from_me: bool
    lines: list[str] = field(default_factory=list)

    @property
    def text(self):
        return "\n".join(self.lines)


def clean(text):
    """Redact contact details, drop link-only and attachment-only messages. Returns None to drop."""
    text = text.replace(OBJECT_REPLACEMENT, "").strip()
    text = EMAIL_RE.sub("[email]", text)
    text = PHONE_RE.sub("[phone]", text)
    if not URL_RE.sub("", text).strip():
        return None
    return text


def conversations(messages, gap=DEFAULT_GAP):
    """Split each chat into conversations wherever the silence exceeds `gap`."""
    ordered = sorted(messages, key=lambda m: (m.chat_id, m.timestamp))
    for _, chat_msgs in groupby(ordered, key=lambda m: m.chat_id):
        current, last_ts = [], None
        for msg in chat_msgs:
            if last_ts is not None and msg.timestamp - last_ts > gap:
                yield current
                current = []
            current.append(msg)
            last_ts = msg.timestamp
        if current:
            yield current


def to_turns(conversation):
    """Merge consecutive messages from the same sender into a single turn (texting in bursts)."""
    turns = []
    for msg in conversation:
        text = clean(msg.text)
        if text is None:
            continue
        if turns and turns[-1].is_from_me == msg.is_from_me:
            turns[-1].lines.append(text)
        else:
            turns.append(Turn(msg.is_from_me, [text]))
    return turns


def build_pairs(messages, gap=DEFAULT_GAP, context_turns=4):
    """Return training examples: each of my turns with the turns leading up to it."""
    pairs = []
    for convo in conversations(messages, gap):
        turns = to_turns(convo)
        for i, turn in enumerate(turns):
            if turn.is_from_me and i > 0 and not turns[i - 1].is_from_me:
                context = turns[max(0, i - context_turns) : i]
                pairs.append(
                    {
                        "context": [{"role": "me" if t.is_from_me else "them", "text": t.text} for t in context],
                        "prompt": turns[i - 1].text,
                        "response": turn.text,
                    }
                )
    return pairs


def my_messages(messages):
    """My individual cleaned messages (used for style statistics)."""
    out = []
    for m in messages:
        if m.is_from_me and (text := clean(m.text)):
            out.append(text)
    return out
