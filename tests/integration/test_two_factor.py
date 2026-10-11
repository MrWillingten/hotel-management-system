"""Two-factor sign-in (story 6.1): enrolment, the code step, recovery codes, reset."""

from datetime import timedelta

import pytest

from hotel.domain.actor import Actor
from hotel.domain.errors import (
    AuthenticationError,
    BusinessRuleViolation,
    PermissionDeniedError,
    ValidationError,
)
from hotel.domain.totp import GRACE, totp
from hotel.services.auth import hash_token
from tests.conftest import MANAGER_PASSWORD, enrol_two_factor

STEP = timedelta(seconds=30)


def _login(services, username="mona", password=MANAGER_PASSWORD):
    return services.auth.login(username, password, ip="10.0.0.1", user_agent="pytest")


def _code(services, secret):
    return totp(secret, services.clock.now())


def _actions(services):
    with services.uow_factory() as uow:
        return [entry.action for entry in uow.audit.iterate()]


@pytest.fixture
def secret(services, manager, clock):
    secret = enrol_two_factor(services, manager)
    clock.advance(STEP)  # the enrolment code cannot be used again to sign in
    return secret


# ------------------------------------------------------------ enrolment
def test_enrolment_keeps_the_secret_until_confirmed(services, manager):
    actor = Actor(manager)
    first = services.two_factor.begin(actor, issuer="Hotel")
    assert services.two_factor.begin(actor, issuer="Hotel").secret == first.secret
    assert first.uri.startswith("otpauth://totp/Hotel:mona?secret=")
    assert not services.two_factor.status(actor).enabled
    with pytest.raises(ValidationError, match="wrong_code"):
        services.two_factor.confirm(actor, "12345")
    codes = services.two_factor.confirm(actor, _code(services, first.secret))
    assert len(codes) == 10
    status = services.two_factor.status(actor)
    assert status.enabled
    assert status.recovery_codes_left == 10
    assert status.required
    with pytest.raises(BusinessRuleViolation, match="already_enabled"):
        services.two_factor.begin(actor, issuer="Hotel")
    with pytest.raises(BusinessRuleViolation, match="already_enabled"):
        services.two_factor.confirm(actor, "123456")
    assert "totp.enabled" in _actions(services)
    with services.uow_factory() as uow:  # only hashes are stored
        rows = uow._conn.execute("SELECT code_hash FROM recovery_code").fetchall()
    assert codes[0] not in {row[0] for row in rows}


def test_anonymous_actors_have_no_second_factor(services):
    with pytest.raises(PermissionDeniedError):
        services.two_factor.status(Actor.system())


# ------------------------------------------------------------ signing in
def test_password_alone_opens_no_session_once_enrolled(services, manager, secret):
    result = _login(services)
    assert result.needs_code
    assert result.token is None
    session = services.auth.complete_login(result.challenge, _code(services, secret), ip="10.0.0.1")
    assert services.auth.authenticate_session(session.token).id == manager.id
    actions = _actions(services)
    assert actions[-2:] == ["auth.password_accepted", "auth.login"]
    # The challenge is gone: it cannot open a second session.
    with pytest.raises(AuthenticationError, match="code_expired"):
        services.auth.complete_login(result.challenge, _code(services, secret), ip="10.0.0.1")


def test_a_code_cannot_be_used_twice(services, manager, secret):
    code = _code(services, secret)
    services.auth.complete_login(_login(services).challenge, code, ip="10.0.0.1")
    with pytest.raises(AuthenticationError, match="invalid_code"):
        services.auth.complete_login(_login(services).challenge, code, ip="10.0.0.1")


def test_wrong_codes_count_towards_the_lockout(services, manager, secret):
    challenge = _login(services).challenge
    for _ in range(4):
        with pytest.raises(AuthenticationError, match="invalid_code"):
            services.auth.complete_login(challenge, "000000", ip="10.0.0.1")
    # The fifth failure locks the account and drops the challenge.
    with pytest.raises(AuthenticationError, match="code_expired"):
        services.auth.complete_login(challenge, "000000", ip="10.0.0.1")
    assert "auth.code_failed" in _actions(services)
    with pytest.raises(AuthenticationError, match="invalid_credentials"):
        _login(services)  # locked for 15 minutes, even with the right password


def test_too_many_wrong_codes_need_the_password_again(services, manager, secret):
    services.auth._settings = type(services.auth._settings)(challenge_max_attempts=2)
    challenge = _login(services).challenge
    with pytest.raises(AuthenticationError, match="invalid_code"):
        services.auth.complete_login(challenge, "000000", ip="10.0.0.1")
    with pytest.raises(AuthenticationError, match="code_expired"):
        services.auth.complete_login(challenge, "000000", ip="10.0.0.1")
    with pytest.raises(AuthenticationError, match="code_expired"):
        services.auth.complete_login(challenge, _code(services, secret), ip="10.0.0.1")


def test_a_locked_account_cannot_finish_signing_in(services, manager, secret):
    challenge = _login(services).challenge
    with services.uow_factory() as uow:
        user = uow.users.get(manager.id)
        user.locked_until = services.clock.now() + timedelta(minutes=5)
        uow.users.update(user)
    with pytest.raises(AuthenticationError, match="invalid_credentials"):
        services.auth.complete_login(challenge, _code(services, secret), ip="10.0.0.1")


def test_the_code_step_expires_after_five_minutes(services, manager, secret, clock):
    challenge = _login(services).challenge
    clock.advance(timedelta(minutes=5))
    with pytest.raises(AuthenticationError, match="code_expired"):
        services.auth.complete_login(challenge, _code(services, secret), ip="10.0.0.1")


@pytest.mark.parametrize("challenge", [None, "", "x" * 200, "unknown"])
def test_missing_or_forged_challenges_are_refused(services, manager, secret, challenge):
    with pytest.raises(AuthenticationError, match="code_expired"):
        services.auth.complete_login(challenge, "123456", ip="10.0.0.1")


def test_deactivated_accounts_cannot_finish_signing_in(services, hotel, clock):
    rita = hotel.rita.user
    secret = enrol_two_factor(services, rita)
    clock.advance(STEP)
    challenge = _login(services, "rita").challenge
    with services.uow_factory() as uow:
        user = uow.users.get(rita.id)
        user.is_active = False
        uow.users.update(user)
    with pytest.raises(AuthenticationError, match="code_expired"):
        services.auth.complete_login(challenge, _code(services, secret), ip="10.0.0.1")


# ------------------------------------------------------------ recovery codes
def test_each_recovery_code_works_once(services, manager, clock):
    actor = Actor(manager)
    secret = services.two_factor.begin(actor, issuer="Hotel").secret
    codes = services.two_factor.confirm(actor, _code(services, secret))
    result = services.auth.complete_login(_login(services).challenge, codes[3], ip="10.0.0.1")
    assert result.token
    assert "auth.recovery_code_used" in _actions(services)
    assert services.two_factor.status(actor).recovery_codes_left == 9
    with pytest.raises(AuthenticationError, match="invalid_code"):
        services.auth.complete_login(_login(services).challenge, codes[3], ip="10.0.0.1")


def test_new_recovery_codes_replace_the_old_ones(services, manager, clock):
    actor = Actor(manager)
    secret = services.two_factor.begin(actor, issuer="Hotel").secret
    old = services.two_factor.confirm(actor, _code(services, secret))
    clock.advance(STEP)
    with pytest.raises(ValidationError, match="wrong_code"):
        services.two_factor.regenerate_codes(actor, "000000")
    new = services.two_factor.regenerate_codes(actor, _code(services, secret))
    assert not set(old) & set(new)
    with pytest.raises(AuthenticationError, match="invalid_code"):
        services.auth.complete_login(_login(services).challenge, old[0], ip="10.0.0.1")
    assert services.auth.complete_login(_login(services).challenge, new[0], ip="10.0.0.1").token


def test_codes_are_needed_to_renew_when_not_enrolled(services, manager):
    with pytest.raises(BusinessRuleViolation, match="not_enabled"):
        services.two_factor.regenerate_codes(Actor(manager), "123456")


# ------------------------------------------------------------ turning off, reset
def test_receptionists_may_turn_it_off_but_managers_may_not(services, hotel, clock):
    rita = hotel.rita.user
    secret = enrol_two_factor(services, rita)
    clock.advance(STEP)
    with pytest.raises(BusinessRuleViolation, match="required_for_managers"):
        services.two_factor.disable(hotel.boss, "123456")
    with pytest.raises(ValidationError):
        services.two_factor.disable(hotel.rita, "000000")
    services.two_factor.disable(hotel.rita, _code(services, secret))
    assert not services.two_factor.status(hotel.rita).enabled
    assert _login(services, "rita").token  # back to the password alone
    assert "totp.disabled" in _actions(services)


def test_reset_forgets_the_phone_and_ends_sessions(services, manager, secret, hotel):
    challenge = _login(services).challenge
    token = services.auth.complete_login(challenge, _code(services, secret), ip="10.0.0.1").token
    with pytest.raises(PermissionDeniedError):
        services.two_factor.reset(hotel.rita, manager.id)
    services.two_factor.reset(Actor.system(), manager.id)
    assert services.auth.authenticate_session(token) is None
    with services.uow_factory() as uow:
        user = uow.users.get(manager.id)
        assert uow.recovery_codes.remaining(manager.id) == 0
    assert not user.two_factor.enabled
    assert user.must_enrol_two_factor(services.clock.now())  # straight to the new phone
    assert "totp.reset" in _actions(services)


# ------------------------------------------------------------ the grace period
def test_a_manager_grace_period_starts_at_the_first_sign_in(services, hotel, clock):
    assert _login(services).token
    with services.uow_factory() as uow:
        boss, rita = uow.users.get(hotel.boss.user.id), uow.users.get(hotel.rita.user.id)
    assert boss.two_factor.grace_until == clock.now() + GRACE
    assert not boss.must_enrol_two_factor(clock.now())
    assert boss.must_enrol_two_factor(clock.now() + GRACE)
    _login(services, "rita")
    with services.uow_factory() as uow:
        rita = uow.users.get(hotel.rita.user.id)
    assert rita.two_factor.grace_until is None  # receptionists are never required
    assert not rita.must_enrol_two_factor(clock.now() + GRACE * 10)


def test_challenge_tokens_are_stored_hashed(services, manager, secret):
    challenge = _login(services).challenge
    with services.uow_factory() as uow:
        assert uow.login_challenges.get(challenge) is None
        assert uow.login_challenges.get(hash_token(challenge)) is not None
