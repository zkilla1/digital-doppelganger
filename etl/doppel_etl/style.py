"""Quantify texting style so the chatbot prompt can describe it precisely."""

import re
import statistics
from collections import Counter

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U0001F000-\U0001F02F]"
)
WORD_RE = re.compile(r"[a-z']+")
LAUGHS = ("lol", "lmao", "lmfao", "haha", "hahaha", "rofl", "💀", "😂")
STOPWORDS = set(
    "a an the and or but if to of in on at for with is are was were be been it its this that i you he she we they "
    "me my your our their im i'm it's dont don't do does did so just not no yes ok okay".split()
)


def _ratio(count, total):
    return round(count / total, 3) if total else 0.0


def analyze(messages, top_n=15):
    if not messages:
        raise ValueError("no messages from you were found")

    word_counts = [len(m.split()) for m in messages]
    words = [w for m in messages for w in WORD_RE.findall(m.lower())]
    emojis = Counter(e for m in messages for e in EMOJI_RE.findall(m))

    ngrams = Counter()
    for m in messages:
        tokens = WORD_RE.findall(m.lower())
        for n in (2, 3):
            for i in range(len(tokens) - n + 1):
                gram = tokens[i : i + n]
                if not all(t in STOPWORDS for t in gram):
                    ngrams[" ".join(gram)] += 1

    lower_text = " ".join(messages).lower()
    laugh_counts = {l: len(re.findall(rf"(?<![a-z]){re.escape(l)}(?![a-z])", lower_text)) for l in LAUGHS}

    openers = Counter(WORD_RE.findall(m.lower())[0] for m in messages if WORD_RE.findall(m.lower()))

    return {
        "message_count": len(messages),
        "avg_words": round(statistics.mean(word_counts), 1),
        "median_words": statistics.median(word_counts),
        "lowercase_start_ratio": _ratio(sum(1 for m in messages if m[:1].islower()), len(messages)),
        "ends_with_period_ratio": _ratio(sum(1 for m in messages if m.rstrip().endswith(".")), len(messages)),
        "question_ratio": _ratio(sum(1 for m in messages if "?" in m), len(messages)),
        "exclamation_ratio": _ratio(sum(1 for m in messages if "!" in m), len(messages)),
        "emoji_message_ratio": _ratio(sum(1 for m in messages if EMOJI_RE.search(m)), len(messages)),
        "top_emojis": [e for e, _ in emojis.most_common(10)],
        "laughs": {k: v for k, v in sorted(laugh_counts.items(), key=lambda kv: -kv[1]) if v},
        "top_phrases": [g for g, c in ngrams.most_common(top_n) if c > 1],
        "top_openers": [w for w, _ in openers.most_common(8)],
        "vocabulary_size": len(set(words)),
    }


def describe(stats, name="the user"):
    """Turn the stats into plain-language rules for a system prompt."""
    rules = [f"Keep replies short: about {stats['avg_words']:.0f} words per message, like {name} does."]
    if stats["lowercase_start_ratio"] > 0.6:
        rules.append("Usually start messages in lowercase.")
    if stats["ends_with_period_ratio"] < 0.2:
        rules.append("Rarely end messages with a period.")
    if stats["emoji_message_ratio"] > 0.1 and stats["top_emojis"]:
        rules.append(f"Use emoji sometimes, mostly {' '.join(stats['top_emojis'][:5])}.")
    elif stats["emoji_message_ratio"] <= 0.03:
        rules.append("Almost never use emoji.")
    if stats["laughs"]:
        favorite = next(iter(stats["laughs"]))
        rules.append(f'When something is funny, react with "{favorite}".')
    if stats["top_phrases"]:
        rules.append(f"Phrases {name} uses a lot: {', '.join(stats['top_phrases'][:8])}.")
    return rules
