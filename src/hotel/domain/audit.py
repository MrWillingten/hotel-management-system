"""Tamper-evident audit trail.

Every entry stores the SHA-256 of (previous entry's hash + its own content).
Changing or removing any past entry breaks every hash that follows it, so
`verify_chain` can tell exactly where the history was altered.

What this does NOT do: prevent tampering. Someone with direct access to the
database file could rewrite the whole chain from the altered row onward. It
makes silent edits detectable, which is what an audit trail needs; keeping a
copy of the latest hash elsewhere (e.g. printed by `hotel audit verify`)
closes that gap.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

GENESIS_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class AuditEntry:
    at: datetime
    action: str  # dotted code, e.g. "room.created"
    user_id: int | None = None
    username: str | None = None  # copied, so the entry stays readable if the user changes
    entity: str | None = None
    entity_id: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    ip: str | None = None
    id: int | None = None
    prev_hash: str = ""
    hash: str = ""

    def canonical(self) -> str:
        """A stable text form of the content: same entry, same text, same hash."""
        return json.dumps(
            {
                "at": self.at.astimezone(UTC).isoformat(timespec="microseconds"),
                "action": self.action,
                "user_id": self.user_id,
                "username": self.username,
                "entity": self.entity,
                "entity_id": self.entity_id,
                "details": dict(self.details),
                "ip": self.ip,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )


def chain_hash(prev_hash: str, entry: AuditEntry) -> str:
    return hashlib.sha256(f"{prev_hash}\n{entry.canonical()}".encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ChainCheck:
    ok: bool
    checked: int
    broken_at: int | None = None  # id of the first entry that no longer matches
    reason: str | None = None  # "link": an earlier entry was removed or replaced
    last_hash: str = GENESIS_HASH  # "content": this entry was edited


def verify_chain(entries: Iterable[AuditEntry]) -> ChainCheck:
    previous = GENESIS_HASH
    checked = 0
    for entry in entries:
        checked += 1
        if entry.prev_hash != previous:
            return ChainCheck(False, checked, entry.id, "link", previous)
        if chain_hash(previous, entry) != entry.hash:
            return ChainCheck(False, checked, entry.id, "content", previous)
        previous = entry.hash
    return ChainCheck(True, checked, last_hash=previous)
