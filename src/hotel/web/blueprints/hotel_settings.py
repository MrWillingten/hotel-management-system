"""Hotel settings and tax rules, kept by managers (story 4.8)."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import get_locale
from flask_babel import gettext as _

from hotel.domain.enums import Role
from hotel.domain.errors import HotelError, NotFoundError, ValidationError
from hotel.domain.settings import HotelSettings
from hotel.domain.taxes import PerAdultNightTax, PercentTax, TaxBase, TaxKind, TaxPayers, TaxRule
from hotel.web import forms
from hotel.web.context import current_actor, services
from hotel.web.countries import country_code, country_name, country_options
from hotel.web.security import roles_required

bp = Blueprint("settings", __name__, url_prefix="/settings")


def _hotel_settings(data) -> HotelSettings:
    return HotelSettings(
        check_in_time=forms.clock_time(data, "check_in_time"),
        check_out_time=forms.clock_time(data, "check_out_time"),
        cancellation_fee_bp=forms.percent(data, "cancellation_fee"),
        cancellation_window_hours=forms.integer(data, "cancellation_window_hours"),
        grace_period_hours=forms.integer(data, "grace_period_hours"),
        discount_cap_bp=forms.percent(data, "discount_cap"),
        weekend_surcharge_bp=forms.percent(data, "weekend_surcharge"),
        anonymise_after_months=forms.integer(data, "anonymise_after_months"),
        # Checkboxes named weekend_<weekday>; only 0-6 can ever be stored.
        weekend_nights=",".join(str(d) for d in range(7) if forms.checkbox(data, f"weekend_{d}")),
        home_country=country_code(forms.text(data, "home_country", max_length=60)) or "TN",
    )


def _tax_rule(data, *, version: int = 1, is_active: bool = True) -> TaxRule:
    """Build the right Strategy class from the form: the "rate" field is a
    percentage for PERCENT rules and an amount in dinars for per-night rules."""
    try:
        kind = TaxKind(data.get("kind", ""))
        applies_to = TaxBase(data.get("applies_to", ""))
        payers = TaxPayers(data.get("payers", "EVERYONE"))
    except ValueError:
        raise ValidationError("tax.kind_invalid", fields={"kind": "tax.kind_invalid"}) from None
    common = {
        "name": forms.text(data, "name", max_length=60),
        "applies_to": applies_to,
        "payers": payers,
        "is_active": is_active,
        "version": version,
    }
    if kind is TaxKind.PERCENT:
        return PercentTax(rate_bp=forms.percent(data, "rate"), **common)
    return PerAdultNightTax(amount_per=forms.money(data, "rate"), **common)


def _page(errors=None, values=None, *, tax_errors=None, tax_values=None, status=200):
    actor = current_actor()
    settings = services().hotel_settings.get(actor)
    return render_template(
        "settings/index.html",
        settings=settings,
        countries=country_options(_locale()),
        home_country_name=country_name(settings.home_country, _locale()),
        rules=services().hotel_settings.tax_rules(actor),
        errors=errors or forms.FormErrors(),
        values=values or {},
        tax_errors=tax_errors or forms.FormErrors(),
        tax_values=tax_values or {},
    ), status


@bp.get("/")
@roles_required(Role.MANAGER)
def index():
    return _page()


@bp.post("/")
@roles_required(Role.MANAGER)
def update():
    try:
        services().hotel_settings.update(current_actor(), _hotel_settings(request.form))
    except HotelError as exc:
        return _page(forms.FormErrors.from_error(exc), request.form, status=400)
    flash(_("Settings saved."), "success")
    return redirect(url_for("settings.index"))


@bp.post("/taxes")
@roles_required(Role.MANAGER)
def create_tax():
    try:
        rule = services().hotel_settings.create_tax_rule(current_actor(), _tax_rule(request.form))
    except HotelError as exc:
        errors = forms.FormErrors.from_error(exc)
        return _page(tax_errors=errors, tax_values=request.form, status=400)
    flash(_("Tax rule %(name)s added.", name=rule.name), "success")
    return redirect(url_for("settings.index"))


@bp.route("/taxes/<int:rule_id>/edit", methods=["GET", "POST"])
@roles_required(Role.MANAGER)
def edit_tax(rule_id: int):
    actor = current_actor()
    rules = {r.id: r for r in services().hotel_settings.tax_rules(actor)}
    if rule_id not in rules:
        raise NotFoundError(entity="tax_rule", id=rule_id)
    errors, values = forms.FormErrors(), None
    if request.method == "POST":
        values = request.form
        try:
            services().hotel_settings.update_tax_rule(
                actor,
                rule_id,
                _tax_rule(
                    values,
                    version=forms.integer(values, "version"),
                    is_active=forms.checkbox(values, "is_active"),
                ),
            )
        except HotelError as exc:
            errors = forms.FormErrors.from_error(exc)
        else:
            flash(_("Changes saved."), "success")
            return redirect(url_for("settings.index"))
    home = services().hotel_settings.get(actor).home_country
    return render_template(
        "settings/tax.html",
        rule=rules[rule_id],
        errors=errors,
        values=values,
        home_country_name=country_name(home, _locale()),
    ), (400 if errors else 200)


def _locale() -> str:
    return str(get_locale() or "en")
