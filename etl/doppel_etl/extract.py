"""Extract messages from an iMessage chat.db (macOS) or a CSV export."""

import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Message:
    chat_id: str
    timestamp: datetime
    is_from_me: bool
    text: str


def apple_time(value):
    """chat.db stores seconds (older macOS) or nanoseconds (High Sierra+) since 2001-01-01."""
    if value is None:
        return APPLE_EPOCH
    if value > 1e11:
        value = value / 1e9
    return APPLE_EPOCH + timedelta(seconds=value)


def decode_attributed_body(blob):
    """Pull the plain string out of an NSAttributedString typedstream.

    Since macOS Ventura many rows have message.text = NULL and the content lives only in
    attributedBody. The string follows the 'NSString' class marker as a length-prefixed run:
    one length byte, or 0x81 + uint16 LE, or 0x82 + uint32 LE.
    """
    if not blob:
        return None
    marker = blob.find(b"NSString")
    if marker == -1:
        return None
    start = blob.find(b"+", marker)
    if start == -1:
        return None
    i = start + 1
    length = blob[i]
    i += 1
    if length == 0x81:
        length = int.from_bytes(blob[i : i + 2], "little")
        i += 2
    elif length == 0x82:
        length = int.from_bytes(blob[i : i + 4], "little")
        i += 4
    return blob[i : i + length].decode("utf-8", errors="replace")


def from_chat_db(path):
    """Yield Messages from chat.db. Tapback reactions (associated_message_type != 0) are skipped."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT COALESCE(c.chat_identifier, h.id, 'unknown') AS chat_id,
                   m.date, m.is_from_me, m.text, m.attributedBody
            FROM message m
            LEFT JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
            LEFT JOIN chat c ON c.ROWID = cmj.chat_id
            LEFT JOIN handle h ON h.ROWID = m.handle_id
            WHERE COALESCE(m.associated_message_type, 0) = 0
            ORDER BY m.date
            """
        )
        for chat_id, date, is_from_me, text, body in rows:
            text = text or decode_attributed_body(body)
            if text:
                yield Message(chat_id, apple_time(date), bool(is_from_me), text)
    finally:
        conn.close()


def from_csv(path, me="me"):
    """CSV columns: timestamp (ISO 8601), sender, text, and optional chat. Rows where sender == me are yours.

    Without a chat column the whole file is treated as one conversation thread.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ts = datetime.fromisoformat(row["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            text = (row.get("text") or "").strip()
            if text:
                yield Message(
                    chat_id=row.get("chat") or "default",
                    timestamp=ts,
                    is_from_me=row["sender"].strip().lower() == me.lower(),
                    text=text,
                )
