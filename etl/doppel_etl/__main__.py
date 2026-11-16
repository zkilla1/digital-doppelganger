"""python -m doppel_etl --chat-db ~/Library/Messages/chat.db --name Zach --out ../server/data"""

import argparse
from datetime import timedelta
from pathlib import Path

from . import extract, style, transform
from .load import write_outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a texting persona from iMessage history.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--chat-db", type=Path, help="Path to a copy of ~/Library/Messages/chat.db")
    src.add_argument("--csv", type=Path, help="CSV export with timestamp,sender,text[,chat] columns")
    parser.add_argument("--me", default="me", help="Sender value that marks your own rows in --csv mode")
    parser.add_argument("--name", required=True, help="Your first name, used in the persona prompt")
    parser.add_argument("--out", type=Path, default=Path("../server/data"))
    parser.add_argument("--gap-minutes", type=int, default=30, help="Silence that starts a new conversation")
    args = parser.parse_args(argv)

    messages = list(extract.from_chat_db(args.chat_db) if args.chat_db else extract.from_csv(args.csv, args.me))
    pairs = transform.build_pairs(messages, gap=timedelta(minutes=args.gap_minutes))
    stats = style.analyze(transform.my_messages(messages))
    out = write_outputs(args.out, args.name, stats, pairs)

    print(f"Processed {len(messages)} messages ({stats['message_count']} from you) into {len(pairs)} reply examples.")
    print(f"Wrote persona.json, examples.jsonl, finetune.jsonl to {out.resolve()}")


if __name__ == "__main__":
    main()
