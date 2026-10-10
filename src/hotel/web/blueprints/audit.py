"""Audit log viewer (managers only)."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from hotel.domain.enums import Role
from hotel.domain.errors import ValidationError
from hotel.services.audit import AuditFilter
from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.security import roles_required

bp = Blueprint("audit", __name__, url_prefix="/audit")

# Prefixes offered in the "action" filter.
ACTION_GROUPS = ("auth.", "user.", "room.", "guest.", "backup.")


@bp.get("/")
@roles_required(Role.MANAGER)
def index():
    audit = services().audit
    actor = current_actor()
    args = request.args
    error = None
    try:
        filters = AuditFilter(
            user_id=forms.integer(args, "user", required=False),
            action_prefix=args.get("action") if args.get("action") in ACTION_GROUPS else None,
            since=forms.calendar_date(args, "since", required=False),
            until=forms.calendar_date(args, "until", required=False),
        )
    except ValidationError as exc:
        error = forms.FormErrors.from_error(exc)
        filters = AuditFilter()
    return render_template(
        "audit/index.html",
        page=audit.search(actor, filters, forms.page_request(args, per_page=50)),
        check=audit.verify(actor),
        users=audit.known_users(actor),
        groups=ACTION_GROUPS,
        filters=filters,
        error=error,
    )
