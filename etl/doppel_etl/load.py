"""Write the persona and example files consumed by the chat server."""

import json
from pathlib import Path

from .style import describe


def system_prompt(name, rules):
    return (
        f"You are {name}'s digital doppelganger. Reply to texts exactly the way {name} would: same tone, "
        "slang, length, punctuation and emoji habits. Never say you are an AI unless asked directly.\n"
        "Style rules:\n" + "\n".join(f"- {r}" for r in rules)
    )


def write_outputs(out_dir, name, stats, pairs):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rules = describe(stats, name)
    prompt = system_prompt(name, rules)

    persona = {"name": name, "style": stats, "rules": rules, "system_prompt": prompt}
    (out / "persona.json").write_text(json.dumps(persona, indent=2, ensure_ascii=False), encoding="utf-8")

    with open(out / "examples.jsonl", "w", encoding="utf-8") as fh:
        for pair in pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")

    # OpenAI chat fine-tuning format, for optionally training a dedicated model.
    with open(out / "finetune.jsonl", "w", encoding="utf-8") as fh:
        for pair in pairs:
            messages = [{"role": "system", "content": prompt}]
            for turn in pair["context"]:
                messages.append({"role": "assistant" if turn["role"] == "me" else "user", "content": turn["text"]})
            messages.append({"role": "assistant", "content": pair["response"]})
            fh.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")

    return out
