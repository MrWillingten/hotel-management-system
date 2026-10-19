"""Hotel settings the manager can change (story 4.8)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from datetime import time, timedelta

from hotel.domain.errors import ValidationError
from hotel.domain.guests import COUNTRY_CODES
from hotel.domain.money import BASIS_POINTS_PER_UNIT
from hotel.domain.reservations import CancellationPolicy


@dataclass(frozen=True, slots=True)
class HotelSettings:
    """Defaults are the decisions recorded in docs/requirements.md (Q2, Q3)."""

    check_in_time: time = time(14, 0)
    check_out_time: time = time(12, 0)
    cancellation_fee_bp: int = 2_000  # 20 %
    cancellation_window_hours: int = 48
    grace_period_hours: int = 0
    discount_cap_bp: int = 3_000  # 30 %
    weekend_surcharge_bp: int = 0  # story 5.6; 0 = no weekend price
    weekend_nights: str = "5,6"  # date.weekday() numbers: Saturday and Sunday nights
    anonymise_after_months: int = 24  # story 5.7, decision with the student
    # The hotel's country: decides who is a national for taxes (story 6.16).
    home_country: str = "TN"

    # Allowed ranges, checked by validated(): name -> (lowest, highest).
    _LIMITS = {  # noqa: RUF012 - class constant, not a field (no annotation)
        "cancellation_fee_bp": (0, BASIS_POINTS_PER_UNIT),
        "cancellation_window_hours": (0, 168),
        "grace_period_hours": (0, 72),
        "discount_cap_bp": (0, BASIS_POINTS_PER_UNIT),
        "weekend_surcharge_bp": (0, BASIS_POINTS_PER_UNIT),
        "anonymise_after_months": (6, 120),
    }

    def validated(self) -> HotelSettings:
        """Return self, or raise one ValidationError naming every wrong field."""
        problems = {
            name: "settings.out_of_range"
            for name, (low, high) in self._LIMITS.items()
            if not low <= getattr(self, name) <= high
        }
        days = [d for d in self.weekend_nights.split(",") if d]  # "" means no weekend
        if any(d not in {"0", "1", "2", "3", "4", "5", "6"} for d in days):
            problems["weekend_nights"] = "settings.out_of_range"
        if self.home_country not in COUNTRY_CODES:
            problems["home_country"] = "guest.nationality_invalid"
        if problems:
            raise ValidationError("settings.invalid", fields=problems)
        return self

    @property
    def weekend_days(self) -> frozenset[int]:
        """The weekend nights as weekday numbers (Monday 0 ... Sunday 6)."""
        return frozenset(int(d) for d in self.weekend_nights.split(",") if d.isdigit())

    def cancellation_policy(self) -> CancellationPolicy:
        return CancellationPolicy(
            fee_basis_points=self.cancellation_fee_bp,
            window=timedelta(hours=self.cancellation_window_hours),
            check_in_time=self.check_in_time,
            grace_period=timedelta(hours=self.grace_period_hours),
        )

    # ------------------------------------------------------------ storage as text
    def to_strings(self) -> dict[str, str]:
        return {
            name: value.strftime("%H:%M") if isinstance(value, time) else str(value)
            for name, value in asdict(self).items()
        }

    @classmethod
    def from_strings(cls, stored: dict[str, str]) -> HotelSettings:
        """Read stored values; anything missing or unreadable keeps its default."""
        settings = cls()
        for item in fields(cls):
            raw = stored.get(item.name)
            if raw is None:
                continue
            try:
                if item.type == "time":
                    value = time.fromisoformat(raw)
                elif item.type == "str":
                    value = raw
                else:
                    value = int(raw)
            except ValueError:
                continue
            settings = replace(settings, **{item.name: value})
        return settings
