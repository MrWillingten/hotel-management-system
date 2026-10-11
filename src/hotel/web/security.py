"""Access control and HTTP security for every request.

Deny by default: every view must declare who may use it with exactly one of
@public, @login_required or @roles_required(...). A view without a policy is
refused with 403, and tests/e2e/test_route_policy.py fails the build if any
route forgets its declaration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar
from urllib.parse import urlsplit

from flask import Flask, Response, abort, current_app, g, redirect, request, url_for

from hotel.domain.enums import Role
from hotel.web.context import services, settings

POLICY_ATTRIBUTE = "_hotel_access_policy"
AUTH_COOKIE = "hotel_session"

F = TypeVar("F", bound=Callable[..., object])


@dataclass(frozen=True, slots=True)
class AccessPolicy:
    public: bool = False
    roles: frozenset[Role] | None = None  # None = any signed-in user


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
    token = request.cookies.get(AUTH_COOKIE)
    g.user = services().auth.authenticate_session(token) if token else None
    g.clear_auth_cookie = token is not None and g.user is None


# A user with a temporary password can only do this until it is replaced.
_ALLOWED_BEFORE_PASSWORD_CHANGE = frozenset(
    {"account.change_password", "auth.logout", "preferences.set_theme", "preferences.set_language"}
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
    if g.user is None:
        target = request.full_path.rstrip("?") if request.method == "GET" else None
        return redirect(url_for("auth.login", next=target))
    if g.user.must_change_password and endpoint not in _ALLOWED_BEFORE_PASSWORD_CHANGE:
        return redirect(url_for("account.change_password"))
    if policy.roles is not None and g.user.role not in policy.roles:
        abort(403)
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
        response.delete_cookie(AUTH_COOKIE, path="/")
    return response


def install(app: Flask) -> None:
    app.before_request(load_current_user)
    app.before_request(enforce_access_policy)
    app.after_request(add_security_headers)
