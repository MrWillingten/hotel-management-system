"""The front desk's day at a glance (story 4.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.reservations import Reservation
from hotel.domain.rooms import Housekeeping, Room
from hotel.persistence.unit_of_work import UnitOfWorkFactory
from hotel.services.authorization import require_staff


@dataclass(frozen=True, slots=True)
class Occupancy:
    """Decision H: rooms sold tonight / rooms that could be sold tonight."""

    sold: int
    sellable: int

    @property
    def basis_points(self) -> int:
        """Rate in basis points (7550 = 75.50 %), rounded down; 0 if nothing is sellable."""
        return self.sold * 10_000 // self.sellable if self.sellable else 0


@dataclass(frozen=True, slots=True)
class FrontDeskDay:
    today: date
    arrivals: list[Reservation] = field(default_factory=list)
    departures: list[Reservation] = field(default_factory=list)
    in_house: list[Reservation] = field(default_factory=list)
    to_clean: list[Room] = field(default_factory=list)
    occupancy: Occupancy = Occupancy(0, 0)

    @property
    def guests_in_house(self) -> int:
        return sum(r.occupants for r in self.in_house)


class FrontDeskService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    def day(self, actor: Actor) -> FrontDeskDay:
        """Everything the dashboard shows, read in one transaction so it is consistent."""
        require_staff(actor)
        today = self._clock.today()
        with self._uow() as uow:
            rooms = uow.rooms.list()
            states = uow.maintenance.states_on(today)
            sellable = [r for r in rooms if r.in_service and states.get(r.id) != "MAINTENANCE"]
            sold = sum(1 for r in sellable if states.get(r.id) in ("CONFIRMED", "CHECKED_IN"))
            return FrontDeskDay(
                today=today,
                arrivals=uow.reservations.arrivals(today),
                departures=uow.reservations.departures(today),
                in_house=uow.reservations.in_house(),
                to_clean=[r for r in rooms if r.housekeeping is Housekeeping.DIRTY],
                occupancy=Occupancy(sold, len(sellable)),
            )
