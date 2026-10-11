"""The walk-through for new accounts (story 6.14).

Two parts: a short guided tour (pages in the web layer) and a "Getting
started" checklist. A checklist item is ticked when the audit log shows the
user did it at least once, so nothing extra has to be recorded and the list
can never disagree with what really happened.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChecklistItem:
    key: str
    actions: frozenset[str]  # any of these audit actions ticks the item
    manager_only: bool = False


CHECKLIST: tuple[ChecklistItem, ...] = (
    ChecklistItem("register_guest", frozenset({"guest.created"})),
    ChecklistItem("book", frozenset({"reservation.created"})),
    ChecklistItem("check_in", frozenset({"reservation.checked_in"})),
    ChecklistItem("take_payment", frozenset({"payment.deposit", "payment.payment"})),
    ChecklistItem("check_out", frozenset({"reservation.checked_out"})),
    ChecklistItem("add_room", frozenset({"room.created"}), manager_only=True),
    ChecklistItem("add_staff", frozenset({"user.created"}), manager_only=True),
    ChecklistItem("two_factor", frozenset({"totp.enabled"}), manager_only=True),
    ChecklistItem("backup", frozenset({"backup.created"}), manager_only=True),
)


@dataclass(frozen=True, slots=True)
class Onboarding:
    is_manager: bool
    tour_done: bool
    checklist_dismissed: bool
    done: frozenset[str]  # keys of the ticked items

    @property
    def items(self) -> list[tuple[ChecklistItem, bool]]:
        return [
            (item, item.key in self.done)
            for item in CHECKLIST
            if self.is_manager or not item.manager_only
        ]

    @property
    def progress(self) -> tuple[int, int]:
        ticks = [ticked for _, ticked in self.items]
        return sum(ticks), len(ticks)

    @property
    def show_checklist(self) -> bool:
        done, total = self.progress
        return not self.checklist_dismissed and done < total

    @property
    def show_welcome(self) -> bool:
        return not self.tour_done


def ticked_keys(actions: set[str]) -> frozenset[str]:
    return frozenset(item.key for item in CHECKLIST if item.actions & actions)
