"""The bill of a reservation: preview, discounts, payments, refunds (stories 4.4-4.6)."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _

from hotel.domain.billing import FixedDiscount, PaymentMethod, PercentDiscount
from hotel.domain.enums import Role
from hotel.domain.errors import HotelError, ValidationError
from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.formatting import money
from hotel.web.messages import message_for
from hotel.web.security import login_required, roles_required

bp = Blueprint("billing", __name__, url_prefix="/reservations")


def _to_bill(reservation_id: int):
    return redirect(url_for("billing.bill", reservation_id=reservation_id))


def _method(data) -> PaymentMethod:
    try:
        return PaymentMethod(data.get("method", ""))
    except ValueError:
        raise ValidationError(
            "payment.method_invalid", fields={"method": "payment.method_invalid"}
        ) from None


def _fresh_submission(actor) -> bool:
    """One-time token: a double click must never record the same money twice."""
    if services().form_tokens.consume(actor, request.form.get("form_token")):
        return True
    flash(_("This form was already submitted. Check the payments before trying again."), "warning")
    return False


@bp.get("/<int:reservation_id>/bill")
@login_required
def bill(reservation_id: int):
    actor = current_actor()
    return render_template(
        "billing/bill.html",
        reservation=services().reservations.get(actor, reservation_id),
        bill=services().billing.bill(actor, reservation_id),
        discounts=services().billing.discounts(actor, reservation_id),
        settings=services().hotel_settings.get(actor),
        methods=list(PaymentMethod),
        form_token=services().form_tokens.issue(actor),
    )


@bp.post("/<int:reservation_id>/payments")
@login_required
def pay(reservation_id: int):
    actor = current_actor()
    if _fresh_submission(actor):
        try:
            payment = services().billing.record_payment(
                actor,
                reservation_id,
                amount=forms.money(request.form, "amount"),
                method=_method(request.form),
                reference=forms.text(request.form, "reference", max_length=60),
            )
        except HotelError as exc:
            flash(message_for(exc.code, exc.params), "danger")
        else:
            flash(_("Received %(amount)s.", amount=money(payment.amount)), "success")
    return _to_bill(reservation_id)


@bp.post("/<int:reservation_id>/refunds")
@roles_required(Role.MANAGER)
def refund(reservation_id: int):
    actor = current_actor()
    if _fresh_submission(actor):
        try:
            payment = services().billing.refund(
                actor,
                reservation_id,
                amount=forms.money(request.form, "amount"),
                method=_method(request.form),
                reference=forms.text(request.form, "reference", max_length=60),
            )
        except HotelError as exc:
            flash(message_for(exc.code, exc.params), "danger")
        else:
            flash(_("Refunded %(amount)s.", amount=money(payment.amount)), "success")
    return _to_bill(reservation_id)


@bp.post("/<int:reservation_id>/discounts")
@roles_required(Role.MANAGER)
def grant_discount(reservation_id: int):
    data = request.form
    try:
        reason = forms.text(data, "reason", max_length=200)
        if data.get("kind") == "FIXED":
            discount = FixedDiscount(
                reservation_id=reservation_id, reason=reason, value=forms.money(data, "value")
            )
        else:
            discount = PercentDiscount(
                reservation_id=reservation_id, reason=reason, rate_bp=forms.percent(data, "value")
            )
        services().billing.grant_discount(current_actor(), discount)
    except HotelError as exc:
        flash(message_for(exc.code, exc.params), "danger")
    else:
        flash(_("Discount granted."), "success")
    return _to_bill(reservation_id)


@bp.post("/discounts/<int:discount_id>/remove")
@roles_required(Role.MANAGER)
def remove_discount(discount_id: int):
    reservation_id = forms.integer(request.form, "reservation_id")
    try:
        services().billing.remove_discount(current_actor(), discount_id)
    except HotelError as exc:
        flash(message_for(exc.code, exc.params), "danger")
    else:
        flash(_("Discount removed."), "success")
    return _to_bill(reservation_id)
