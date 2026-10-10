from dataclasses import replace
from datetime import UTC, datetime, timedelta

from hotel.domain.audit import GENESIS_HASH, AuditEntry, chain_hash, verify_chain

T0 = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)


def build_chain(count: int) -> list[AuditEntry]:
    entries, previous = [], GENESIS_HASH
    for i in range(count):
        entry = AuditEntry(
            id=i + 1,
            at=T0 + timedelta(minutes=i),
            action="room.created",
            user_id=1,
            username="mona",
            entity="room",
            entity_id=str(100 + i),
            details={"number": str(100 + i)},
            ip="127.0.0.1",
        )
        digest = chain_hash(previous, entry)
        entries.append(replace(entry, prev_hash=previous, hash=digest))
        previous = digest
    return entries


def test_intact_chain_verifies():
    chain = build_chain(5)
    check = verify_chain(chain)
    assert check.ok
    assert check.checked == 5
    assert check.last_hash == chain[-1].hash


def test_empty_chain_is_intact():
    assert verify_chain([]).ok


def test_edited_entry_is_detected():
    chain = build_chain(5)
    chain[2] = replace(chain[2], details={"number": "999"})
    check = verify_chain(chain)
    assert not check.ok
    assert (check.broken_at, check.reason) == (3, "content")


def test_removed_entry_is_detected():
    chain = build_chain(5)
    del chain[1]
    check = verify_chain(chain)
    assert (check.ok, check.broken_at, check.reason) == (False, 3, "link")


def test_recomputing_one_hash_is_not_enough_to_hide_an_edit():
    chain = build_chain(4)
    edited = replace(chain[1], username="someone-else")
    chain[1] = replace(edited, hash=chain_hash(chain[1].prev_hash, edited))
    check = verify_chain(chain)
    assert (check.broken_at, check.reason) == (3, "link")


def test_canonical_form_is_independent_of_detail_order_and_time_zone():
    from zoneinfo import ZoneInfo

    a = AuditEntry(at=T0, action="x.y", details={"a": 1, "b": 2})
    b = AuditEntry(
        at=T0.astimezone(ZoneInfo("Africa/Tunis")), action="x.y", details={"b": 2, "a": 1}
    )
    assert a.canonical() == b.canonical()
