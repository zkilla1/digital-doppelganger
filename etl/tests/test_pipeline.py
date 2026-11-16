import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from doppel_etl import extract, style, transform
from doppel_etl.__main__ import main
from doppel_etl.extract import Message

T0 = datetime(2025, 3, 1, 18, 0, tzinfo=timezone.utc)


def msg(minutes, me, text, chat="+15550001111"):
    return Message(chat, T0 + timedelta(minutes=minutes), me, text)


def attributed_body(text):
    data = text.encode()
    prefix = bytes([len(data)]) if len(data) < 0x80 else b"\x81" + len(data).to_bytes(2, "little")
    return b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01@\x84\x84\x84\x12NSAttributedString\x00\x84\x84\x08NSObject\x00\x85\x92\x84\x84\x84\x08NSString\x01\x94\x84\x01+" + prefix + data + b"\x86\x84"


def test_decode_attributed_body_short_and_long():
    assert extract.decode_attributed_body(attributed_body("yo what's up")) == "yo what's up"
    long_text = "a" * 300
    assert extract.decode_attributed_body(attributed_body(long_text)) == long_text
    assert extract.decode_attributed_body(None) is None


def test_apple_time_handles_seconds_and_nanoseconds():
    assert extract.apple_time(0) == extract.APPLE_EPOCH
    secs = 700_000_000
    assert extract.apple_time(secs) == extract.apple_time(secs * 1_000_000_000)


def test_clean_redacts_and_drops():
    assert transform.clean("call me at 954-555-1234") == "call me at [phone]"
    assert transform.clean("email zach@example.com") == "email [email]"
    assert transform.clean("https://example.com/x") is None
    assert transform.clean("￼") is None


def test_pairs_merge_bursts_and_split_conversations():
    messages = [
        msg(0, False, "you coming tonight?"),
        msg(1, True, "yeah"),
        msg(1.5, True, "be there at 9"),
        msg(2, False, "bet"),
        # 2 hours later: new conversation, so "bet" must not become context
        msg(120, True, "wait who's driving"),
        msg(121, False, "me"),
        msg(122, True, "perfect lol"),
    ]
    pairs = transform.build_pairs(messages)
    assert [p["response"] for p in pairs] == ["yeah\nbe there at 9", "perfect lol"]
    assert pairs[0]["prompt"] == "you coming tonight?"
    assert [t["text"] for t in pairs[1]["context"]] == ["wait who's driving", "me"]


def test_style_analysis():
    stats = style.analyze(["lol yeah", "nah im good 😂", "lol for real", "see you there"])
    assert stats["message_count"] == 4
    assert stats["lowercase_start_ratio"] == 1.0
    assert "😂" in stats["top_emojis"]
    assert next(iter(stats["laughs"])) == "lol"
    rules = style.describe(stats, "Zach")
    assert any("lowercase" in r for r in rules)


def test_style_requires_messages():
    with pytest.raises(ValueError):
        style.analyze([])


@pytest.fixture
def chat_db(tmp_path):
    path = tmp_path / "chat.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
        CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, chat_identifier TEXT);
        CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
        CREATE TABLE message (ROWID INTEGER PRIMARY KEY, text TEXT, attributedBody BLOB, is_from_me INTEGER,
                              date INTEGER, handle_id INTEGER, associated_message_type INTEGER);
        INSERT INTO handle VALUES (1, '+15550001111');
        INSERT INTO chat VALUES (1, '+15550001111');
        """
    )
    base = int((T0 - extract.APPLE_EPOCH).total_seconds() * 1e9)
    rows = [
        (1, "wanna get food", None, 0, base, 1, 0),
        (2, None, attributed_body("ya im starving"), 1, base + 60_000_000_000, 1, 0),
        (3, "Loved “ya im starving”", None, 0, base + 61_000_000_000, 1, 2000),  # tapback, skipped
        (4, "chipotle?", None, 0, base + 120_000_000_000, 1, 0),
        (5, "say less", None, 1, base + 180_000_000_000, 1, 0),
    ]
    conn.executemany("INSERT INTO message VALUES (?,?,?,?,?,?,?)", rows)
    conn.executemany("INSERT INTO chat_message_join VALUES (1, ?)", [(r[0],) for r in rows])
    conn.commit()
    conn.close()
    return path


def test_chat_db_end_to_end(chat_db, tmp_path, capsys):
    out = tmp_path / "out"
    main(["--chat-db", str(chat_db), "--name", "Zach", "--out", str(out)])

    examples = [json.loads(line) for line in (out / "examples.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["response"] for e in examples] == ["ya im starving", "say less"]

    persona = json.loads((out / "persona.json").read_text(encoding="utf-8"))
    assert persona["style"]["message_count"] == 2
    assert "Zach" in persona["system_prompt"]

    finetune = [json.loads(line) for line in (out / "finetune.jsonl").read_text(encoding="utf-8").splitlines()]
    assert finetune[0]["messages"][-1] == {"role": "assistant", "content": "ya im starving"}
    assert "4 messages" in capsys.readouterr().out


def test_csv_source(tmp_path):
    csv_path = tmp_path / "export.csv"
    csv_path.write_text(
        "timestamp,sender,text\n2025-01-01T10:00:00,Alex,hey\n2025-01-01T10:01:00,me,yo\n", encoding="utf-8"
    )
    messages = list(extract.from_csv(csv_path))
    assert [m.is_from_me for m in messages] == [False, True]
    assert transform.build_pairs(messages)[0]["response"] == "yo"
