"""Access control and HTTP security for every request.

Deny by default: every view must declare who may use it with exactly one of
@public, @login_required or @roles_required(...). A view without a policy is
refused with 403, and tests/e2e/test_route_policy.py fails the build if any
route forgets its declaration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import TypeVar
from urllib.parse import urlsplit

from flask import Flask, Response, abort, current_app, g, jsonify, redirect, request, url_for

from hotel.domain.enums import Role
from hotel.web.context import cookie_name, services, settings
from hotel.web.rate_limit import RateLimiter

POLICY_ATTRIBUTE = "_hotel_access_policy"
AUTH_COOKIE = "hotel_session"

F = TypeVar("F", bound=Callable[..., object])


@dataclass(frozen=True, slots=True)
class AccessPolicy:
    public: bool = False
    roles: frozenset[Role] | None = None  # None = any signed-in user
    api: bool = False  # JSON API: a bearer token instead of the session cookie


def _declare(view: F, policy: AccessPolicy) -> F:
    if hasattr(view, POLICY_ATTRIBUTE):
        raise TypeError(f"{view.__name__} already has an access policy")
    setattr(view, POLICY_ATTRIBUTE, policy)
    return view


def public(view: F) -> F:
    return _declare(view, AccessPolicy(public=True))


def login_required(view: F) -> F:
    return _declare(view, AccessPolicy())


def roles_required(*roles: Role) -> Callable[[F], F]:
    def decorator(view: F) -> F:
        return _declare(view, AccessPolicy(roles=frozenset(roles)))

    return decorator


def api_token_required(view: F) -> F:
    """JSON API views: `Authorization: Bearer <token>`, rate-limited (story 6.3)."""
    return _declare(view, AccessPolicy(api=True))


def policy_of(view: Callable[..., object]) -> AccessPolicy | None:
    return getattr(view, POLICY_ATTRIBUTE, None)


def is_safe_redirect_target(target: str | None) -> bool:
    """Only same-site relative paths, so ?next= cannot send users to another site."""
    if not target or not target.startswith("/") or target.startswith("//"):
        return False
    if "\\" in target or any(ord(c) < 32 for c in target):
        return False
    parts = urlsplit(target)
    return not parts.scheme and not parts.netloc


# ---------------------------------------------------------------- request hooks
def load_current_user() -> None:
    token = request.cookies.get(cookie_name(AUTH_COOKIE))
    g.user = services().auth.authenticate_session(token) if token else None
    g.clear_auth_cookie = token is not None and g.user is None


# A user with a temporary password can only do this until it is replaced.
_ALLOWED_BEFORE_PASSWORD_CHANGE = frozenset(
    {"account.change_password", "auth.logout", "preferences.set_theme", "preferences.set_language"}
)
# A manager whose grace period is over can only set up the second factor (story 6.1).
_ALLOWED_BEFORE_TWO_FACTOR = frozenset(
    {
        "account.two_factor",
        "account.confirm_two_factor",
        "auth.logout",
        "preferences.set_theme",
        "preferences.set_language",
    }
)


def enforce_access_policy() -> Response | None:
    endpoint = request.endpoint
    if endpoint is None or endpoint == "static":
        return None  # unknown URL (404 follows) or a static file
    policy = policy_of(current_app.view_functions[endpoint])
    if policy is None:
        current_app.logger.error("Endpoint %s has no access policy; refusing", endpoint)
        abort(403)
    if policy.public:
        return None
    if policy.api:
        return _authenticate_api_request()
    if g.user is None:
        target = request.full_path.rstrip("?") if request.method == "GET" else None
        return redirect(url_for("auth.login", next=target))
    if g.user.must_change_password and endpoint not in _ALLOWED_BEFORE_PASSWORD_CHANGE:
        return redirect(url_for("account.change_password"))
    if endpoint not in _ALLOWED_BEFORE_TWO_FACTOR and g.user.must_enrol_two_factor(
        services().clock.now()
    ):
        return redirect(url_for("account.two_factor"))
    if policy.roles is not None and g.user.role not in policy.roles:
        abort(403)
    return None


LIMITERS_KEY = "hotel.api_limiters"


def _new_limiters() -> dict[str, RateLimiter]:
    """One set per application: 120 calls a minute per manager is plenty for a
    dashboard and stops a runaway script; an address presenting wrong tokens
    gets 10 tries a minute (256-bit tokens cannot be guessed anyway)."""
    return {
        "calls": RateLimiter(limit=120, window=timedelta(minutes=1)),
        "failures": RateLimiter(limit=10, window=timedelta(minutes=1)),
    }


def api_error(status: int, code: str, *, retry_after: int | None = None) -> Response:
    response = jsonify({"error": code})
    response.status_code = status
    if status == 401:
        response.headers["WWW-Authenticate"] = 'Bearer realm="hotel"'
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response


def _authenticate_api_request() -> Response | None:
    """The API never uses the browser's cookie: a program must show its token.

    That also means a malicious web page cannot make a signed-in browser call
    the API on its behalf.
    """
    g.user = None
    now = services().clock.now()
    address = request.remote_addr or "unknown"
    scheme, _, secret = request.headers.get("Authorization", "").partition(" ")
    user = services().api_tokens.authenticate(secret.strip()) if scheme == "Bearer" else None
    limiters = current_app.extensions[LIMITERS_KEY]
    if user is None:
        wait = limiters["failures"].hit(f"ip:{address}", now)
        if wait:
            return api_error(429, "too_many_requests", retry_after=wait)
        return api_error(401, "unauthorized")
    wait = limiters["calls"].hit(f"user:{user.id}", now)
    if wait:
        return api_error(429, "too_many_requests", retry_after=wait)
    g.api_user = user
    return None


CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "object-src 'none'",
    ]
)


def add_security_headers(response: Response) -> Response:
    headers = response.headers
    headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    headers["X-Content-Type-Options"] = "nosniff"
    headers["X-Frame-Options"] = "DENY"
    headers["Referrer-Policy"] = "same-origin"
    headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    headers["Cross-Origin-Opener-Policy"] = "same-origin"
    if settings().https:
        headers["Strict-Transport-Security"] = "max-age=31536000"
    if request.endpoint != "static":
        # Pages may contain guest data: the back button after logout must not show them.
        headers["Cache-Control"] = "no-store"
    if getattr(g, "clear_auth_cookie", False):
        response.delete_cookie(cookie_name(AUTH_COOKIE), path="/")
    return response


def install(app: Flask) -> None:
    app.extensions[LIMITERS_KEY] = _new_limiters()
    app.before_request(load_current_user)
    app.before_request(enforce_access_policy)
    app.after_request(add_security_headers)
