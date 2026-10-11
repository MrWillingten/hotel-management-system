"""The one-time password algorithm, checked against the RFCs' own test vectors."""

import base64
from datetime import UTC, datetime, timedelta

import pytest

from hotel.domain.errors import ValidationError
from hotel.domain.totp import (
    GRACE,
    RECOVERY_CODES,
    TwoFactor,
    grouped,
    hash_recovery_code,
    hotp,
    looks_like_recovery_code,
    matching_step,
    new_recovery_codes,
    new_secret,
    normalize_code,
    provisioning_uri,
    time_step,
    totp,
)

# The shared key of RFC 4226 and RFC 6238 is the ASCII text "12345678901234567890".
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode("ascii")
NOW = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)


def _at(seconds: int) -> datetime:
    return datetime.fromtimestamp(seconds, UTC)


def test_hotp_matches_rfc_4226_appendix_d():
    expected = ["755224", "287082", "359152", "969429", "338314"]
    expected += ["254676", "287922", "162583", "399871", "520489"]
    assert [hotp(RFC_SECRET, counter) for counter in range(10)] == expected


@pytest.mark.parametrize(
    ("seconds", "code"),
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_totp_matches_rfc_6238_appendix_b(seconds, code):
    # The RFC prints 8-digit SHA-1 codes; authenticator apps use the last 6.
    assert hotp(RFC_SECRET, time_step(_at(seconds)), digits=8) == code
    assert totp(RFC_SECRET, _at(seconds)) == code[-6:]


def test_new_secrets_are_random_160_bit_base32():
    first, second = new_secret(), new_secret()
    assert first != second
    assert len(first) == 32  # 160 bits / 5 bits per character
    assert set(first) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")
    totp(first, NOW)  # decodes without padding


def test_codes_from_the_neighbouring_steps_are_accepted_once():
    secret = new_secret()
    step = time_step(NOW)
    for drift in (-1, 0, 1):
        code = hotp(secret, step + drift)
        assert matching_step(secret, code, NOW, last_used=None) == step + drift
    assert matching_step(secret, hotp(secret, step - 2), NOW, last_used=None) is None
    assert matching_step(secret, hotp(secret, step + 2), NOW, last_used=None) is None
    # Once a step was used, it and every earlier one are refused (no replay).
    assert matching_step(secret, hotp(secret, step), NOW, last_used=step) is None
    assert matching_step(secret, hotp(secret, step + 1), NOW, last_used=step) == step + 1


@pytest.mark.parametrize("bad", ["", "12345", "1234567", "abcdef", "12 34 5x"])
def test_malformed_codes_are_refused(bad):
    assert matching_step(new_secret(), bad, NOW, last_used=None) is None


def test_spaces_and_dashes_are_ignored_when_typing():
    secret = new_secret()
    code = totp(secret, NOW)
    assert matching_step(secret, f" {code[:3]} {code[3:]} ", NOW, last_used=None)
    assert normalize_code("abcd-efgh-2345") == "ABCDEFGH2345"


def test_provisioning_uri_for_authenticator_apps():
    uri = provisioning_uri("ABC", account="mona", issuer="Hotel Jasmin")
    assert uri.startswith("otpauth://totp/Hotel%20Jasmin:mona?")
    assert "secret=ABC" in uri
    assert "issuer=Hotel+Jasmin" in uri
    assert grouped("ABCDEFGHIJ") == "ABCD EFGH IJ"


def test_recovery_codes_are_distinct_unambiguous_and_hashed_loosely():
    codes = new_recovery_codes()
    assert len(set(codes)) == RECOVERY_CODES
    for code in codes:
        assert len(code) == 14
        assert code[4] == code[9] == "-"
        assert not set(code) & set("01ILO")
        assert looks_like_recovery_code(code)
    code = codes[0]
    # Typed in lower case or without dashes, it is still the same code.
    assert hash_recovery_code(code.lower().replace("-", " ")) == hash_recovery_code(code)
    assert len(hash_recovery_code(code)) == 64
    assert not looks_like_recovery_code("123456")


def test_enrolment_needs_one_correct_code():
    state = TwoFactor()
    with pytest.raises(ValidationError, match="not_started"):
        state.confirm_enrolment("123456", NOW)
    secret = state.begin_enrolment()
    assert state.begin_enrolment() == secret  # reloading the page keeps the same secret
    assert not state.enabled
    with pytest.raises(ValidationError, match="wrong_code"):
        state.confirm_enrolment("000000" if totp(secret, NOW) != "000000" else "111111", NOW)
    state.confirm_enrolment(totp(secret, NOW), NOW)
    assert state.enabled
    assert state.secret == secret
    assert state.pending_secret is None
    assert state.enabled_at == NOW
    # The enrolment code itself cannot be replayed to sign in.
    assert not state.accept(totp(secret, NOW), NOW)
    later = NOW + timedelta(seconds=30)
    assert state.accept(totp(secret, later), later)
    assert not state.accept(totp(secret, later), later)


def test_grace_period_and_reset():
    state = TwoFactor()
    assert not state.grace_over(NOW)  # no grace started: nothing is required yet
    state.start_grace(NOW)
    state.start_grace(NOW + timedelta(days=3))  # a second sign-in does not extend it
    assert state.grace_until == NOW + GRACE
    assert not state.grace_over(NOW + GRACE - timedelta(seconds=1))
    assert state.grace_over(NOW + GRACE)
    state.begin_enrolment()
    state.confirm_enrolment(totp(state.pending_secret, NOW), NOW)
    state.reset(NOW)
    assert not state.enabled
    assert state.last_step is None
    assert state.grace_over(NOW)  # after a reset, the new phone is needed at once
    assert not TwoFactor().accept("123456", NOW)
