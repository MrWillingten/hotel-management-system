"""Money in Tunisian dinars.

The dinar is divided into 1000 millimes, so every amount is stored as an
exact integer number of millimes. Floats are never accepted: 0.1 + 0.2 is not
0.3 in binary floating point, and a hotel bill must be exact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from hotel.domain.errors import ValidationError

MILLIMES_PER_DINAR = 1000
BASIS_POINTS_PER_UNIT = 10_000  # 700 basis points = 7.00 %

# Plain machine format: digits, optional dot, at most three decimals.
# Locale-aware input ("1 500,5" in French) is converted to this format by the web layer.
_PLAIN_AMOUNT = re.compile(r"^(\d{1,9})(?:\.(\d{1,3}))?$")


@dataclass(frozen=True, slots=True, order=True)
class Money:
    """An exact amount of money, in millimes. Immutable and compared by value."""

    millimes: int

    def __post_init__(self) -> None:
        # bool is a subclass of int, so it has to be rejected explicitly.
        if not isinstance(self.millimes, int) or isinstance(self.millimes, bool):
            raise TypeError(f"Money needs an int number of millimes, got {self.millimes!r}")

    # ------------------------------------------------------------ factories
    @classmethod
    def zero(cls) -> Money:
        return cls(0)

    @classmethod
    def from_dinars(cls, dinars: int | Decimal) -> Money:
        """Build from a whole or decimal dinar amount that has at most 3 decimals."""
        if isinstance(dinars, float):
            raise TypeError("Use Decimal or int for money, never float")
        millimes = Decimal(dinars) * MILLIMES_PER_DINAR
        if millimes != millimes.to_integral_value():
            raise ValidationError("money.too_many_decimals", value=str(dinars))
        return cls(int(millimes))

    @classmethod
    def parse(cls, text: str) -> Money:
        """Parse a plain amount such as "180", "180.5" or "180.500"."""
        match = _PLAIN_AMOUNT.fullmatch(text.strip())
        if match is None:
            raise ValidationError("money.invalid", value=text)
        whole, fraction = match.group(1), match.group(2) or ""
        return cls(int(whole) * MILLIMES_PER_DINAR + int(fraction.ljust(3, "0")))

    # ------------------------------------------------------------ arithmetic
    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.millimes + other.millimes)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.millimes - other.millimes)

    def __neg__(self) -> Money:
        return Money(-self.millimes)

    def times(self, quantity: int) -> Money:
        """Multiply by a whole quantity (nights, items...)."""
        if not isinstance(quantity, int) or isinstance(quantity, bool):
            raise TypeError("Money can only be multiplied by an int quantity")
        return Money(self.millimes * quantity)

    def percent(self, basis_points: int) -> Money:
        """Return basis_points/10000 of this amount, rounded half-up to the millime.

        Python's built-in round() uses banker's rounding (round(2.5) == 2), which is
        not what an invoice expects, so the rounding mode is chosen explicitly here.
        """
        exact = Decimal(self.millimes) * basis_points / BASIS_POINTS_PER_UNIT
        return Money(int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP)))

    # ------------------------------------------------------------ queries
    def is_zero(self) -> bool:
        return self.millimes == 0

    def is_negative(self) -> bool:
        return self.millimes < 0

    def to_decimal(self) -> Decimal:
        return Decimal(self.millimes).scaleb(-3)

    def __str__(self) -> str:
        sign = "-" if self.millimes < 0 else ""
        dinars, millimes = divmod(abs(self.millimes), MILLIMES_PER_DINAR)
        return f"{sign}{dinars}.{millimes:03d}"
