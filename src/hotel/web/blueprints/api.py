"""Read-only JSON API, version 1 (story 6.3). Documented in docs/api.md.

Every route answers GET only and calls the same services as the pages, so
roles and business rules are checked in one place. The caller is the manager
who owns the token (`g.api_user`). Amounts are integers in millimes
(1 DT = 1000) so no program has to round decimals; dates are ISO 8601.
"""

from __future__ import annotations

from datetime import date

from flask import Blueprint, g, jsonify, request

from hotel.domain.actor import Actor
from hotel.domain.errors import HotelError, NotFoundError, PermissionDeniedError
from hotel.domain.paging import MAX_PER_PAGE, PageRequest
from hotel.domain.period import StayPeriod
from hotel.domain.reservations import Reservation, ReservationStatus
from hotel.persistence.repositories.reservations import ReservationFilter
from hotel.web.context import services
from hotel.web.security import api_error, api_token_required

bp = Blueprint("api", __name__, url_prefix="/api/v1")


class _BadParameter(Exception):
    def __init__(self, name: str) -> None:
        self.name = name


@bp.errorhandler(_BadParameter)
def _bad_parameter(exc: _BadParameter):
    response = jsonify({"error": "invalid_parameter", "parameter": exc.name})
    response.status_code = 400
    return response


@bp.errorhandler(HotelError)
def _hotel_error(exc: HotelError):
    if isinstance(exc, NotFoundError):
        return api_error(404, "not_found")
    if isinstance(exc, PermissionDeniedError):
        return api_error(403, "forbidden")
    response = jsonify({"error": exc.code, "details": {k: str(v) for k, v in exc.params.items()}})
    response.status_code = 400
    return response


def _actor() -> Actor:
    return Actor(user=g.api_user, ip=request.remote_addr, label="api")


def _date(name: str, *, required: bool = True) -> date | None:
    raw = request.args.get(name, "")
    if not raw and not required:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        raise _BadParameter(name) from None


def _int(name: str, default: int, *, low: int = 1, high: int = 10_000) -> int:
    raw = request.args.get(name, "")
    if not raw:
        return default
    if not raw.isdigit() or not low <= int(raw) <= high:
        raise _BadParameter(name)
    return int(raw)


def _reservation(r: Reservation, *, detailed: bool = False) -> dict:
    data = {
        "id": r.id,
        "code": r.code,
        "status": r.status.value,
        "guest": r.guest_name,
        "arrival": r.period.arrival.isoformat(),
        "departure": r.period.departure.isoformat(),
        "nights": r.period.nights,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
    if detailed:
        data["rooms"] = [
            {
                "number": room.number,
                "category": room.category_name,
                "adults": room.adults,
                "children": room.children,
            }
            for room in r.rooms
        ]
        data["accommodation_millimes"] = r.accommodation_total.millimes
    return data


# ---------------------------------------------------------------- routes
@bp.get("/")
@api_token_required
def index():
    """A map of the API, so a program can discover it."""
    return {
        "version": 1,
        "endpoints": [
            "/api/v1/rooms",
            "/api/v1/availability?arrival=YYYY-MM-DD&departure=YYYY-MM-DD&guests=N",
            "/api/v1/reservations?status=&arriving_from=&arriving_until=&page=&per_page=",
            "/api/v1/reservations/<id>",
            "/api/v1/reports/summary?first=YYYY-MM-DD&last=YYYY-MM-DD",
        ],
    }


@bp.get("/rooms")
@api_token_required
def rooms():
    return {
        "rooms": [
            {
                "id": o.room.id,
                "number": o.room.number,
                "category": o.room.category_name,
                "capacity": o.room.capacity,
                "nightly_rate_millimes": o.room.nightly_rate.millimes,
                "in_service": o.room.in_service,
                "tonight": o.status.value,
                "housekeeping": o.room.housekeeping.value,
            }
            for o in services().rooms.list_rooms(_actor())
        ]
    }


@bp.get("/availability")
@api_token_required
def availability():
    arrival, departure = _date("arrival"), _date("departure")
    if departure <= arrival:
        raise _BadParameter("departure")
    found = services().reservations.find_available_rooms(
        _actor(), StayPeriod(arrival, departure), min_capacity=_int("guests", 1, high=50)
    )
    return {
        "arrival": arrival.isoformat(),
        "departure": departure.isoformat(),
        "rooms": [
            {
                "id": room.id,
                "number": room.number,
                "category": room.category_name,
                "capacity": room.capacity,
                "nightly_rate_millimes": room.nightly_rate.millimes,
            }
            for room in found
        ],
    }


@bp.get("/reservations")
@api_token_required
def reservations():
    status_raw = request.args.get("status", "")
    try:
        status = ReservationStatus(status_raw) if status_raw else None
    except ValueError:
        raise _BadParameter("status") from None
    filters = ReservationFilter(
        status=status,
        arriving_from=_date("arriving_from", required=False),
        arriving_until=_date("arriving_until", required=False),
    )
    paging = PageRequest(page=_int("page", 1), per_page=_int("per_page", 20, high=MAX_PER_PAGE))
    page = services().reservations.search(_actor(), filters, paging)
    return {
        "page": page.page,
        "pages": page.pages,
        "total": page.total,
        "reservations": [_reservation(r) for r in page.items],
    }


@bp.get("/reservations/<int:reservation_id>")
@api_token_required
def reservation(reservation_id: int):
    found = services().reservations.get(_actor(), reservation_id)
    return _reservation(found, detailed=True)


@bp.get("/reports/summary")
@api_token_required
def report_summary():
    report = services().reports.report(_actor(), _date("first"), _date("last"))
    return {
        "first": report.first.isoformat(),
        "last": report.last.isoformat(),
        "nights_sold": report.nights_sold,
        "nights_sellable": report.nights_sellable,
        "occupancy_basis_points": report.occupancy_bp,
        "adr_millimes": report.adr.millimes,
        "revpar_millimes": report.revpar.millimes,
        "revenue_millimes": report.revenue.millimes,
        "cash_received_millimes": report.cash_received.millimes,
        "reservations_made": report.reservations_made,
        "cancellations": report.cancellations.count,
        "no_shows": report.no_shows.count,
        "outstanding_millimes": report.outstanding.millimes,
    }
