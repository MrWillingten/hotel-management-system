"""Delete or archive (story 6.17), the same rule for every kind of record.

* A record that was never used (no stay, no charge, no recorded action...)
  is **deleted**: nothing refers to it, so nothing is lost.
* A record with history is **archived**: it disappears from lists, forms and
  suggestions, but stays in the database, because invoices, past stays and
  the audit log must keep pointing to it (BR22, BR26, threat A10). It can be
  restored.
* Some removals are **blocked** whatever the history: a room with future
  bookings, a guest in the house, the last manager... The page says why.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RemovalAction(StrEnum):
    DELETE = "DELETE"
    ARCHIVE = "ARCHIVE"


@dataclass(frozen=True, slots=True)
class RemovalPlan:
    action: RemovalAction
    uses: int  # how many pieces of history refer to the record
    blocked: str | None = None  # an error code when the removal is not allowed now
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.blocked is None


def plan_removal(uses: int, *, blocked: str | None = None, **params: Any) -> RemovalPlan:
    action = RemovalAction.DELETE if uses == 0 else RemovalAction.ARCHIVE
    return RemovalPlan(action, uses, blocked, params)
