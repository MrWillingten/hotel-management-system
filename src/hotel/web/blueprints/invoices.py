"""Issued invoices: list and printable page (story 4.7)."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.security import login_required

bp = Blueprint("invoices", __name__, url_prefix="/invoices")


@bp.get("/")
@login_required
def index():
    query = request.args.get("q", "")[:50].strip()
    page = services().invoices.search(current_actor(), query, forms.page_request(request.args))
    return render_template("invoices/index.html", page=page, query=query)


@bp.get("/<int:invoice_id>")
@login_required
def detail(invoice_id: int):
    actor = current_actor()
    return render_template(
        "invoices/detail.html",
        invoice=services().invoices.get(actor, invoice_id),
        settings=services().hotel_settings.get(actor),
    )
