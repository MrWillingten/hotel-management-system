"""Registering, finding and updating guests."""

from __future__ import annotations

from datetime import date

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    StaleDataError,
    ValidationError,
)
from hotel.domain.guests import Guest, GuestDetails, IdDocType, months_before
from hotel.domain.paging import Page, PageRequest
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.authorization import require_role, require_staff
from hotel.services.hotel_settings import load_settings

MAX_REASON = 200


class ProbableDuplicateError(ConflictError):
    """Another guest has the same name and phone or e-mail; the user must confirm."""

    code = "guest.probable_duplicate"

    def __init__(self, candidates: list[Guest]) -> None:
        super().__init__(count=len(candidates))
        self.candidates = candidates


class GuestService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    def search(
        self, actor: Actor, query: str, request: PageRequest, *, sort: str = "name"
    ) -> Page[Guest]:
        require_staff(actor)
        with self._uow() as uow:
            return uow.guests.search(query.strip()[:100], request, sort=sort)

    def get(self, actor: Actor, guest_id: int) -> Guest:
        require_staff(actor)
        with self._uow() as uow:
            return self._load(uow, guest_id)

    def register(
        self, actor: Actor, details: GuestDetails, *, confirm_duplicate: bool = False
    ) -> Guest:
        """Scenario §4.2: a returning guest must be found, not registered twice."""
        require_staff(actor)
        details = details.cleaned()
        guest = Guest(
            id=None,
            first_name="",
            last_name="",
            id_doc_type=IdDocType.CIN,
            id_doc_number="",
            created_at=self._clock.now(),
        )
        guest.apply(details)
        with self._uow() as uow:
            self._refuse_same_document(uow, guest)
            if not confirm_duplicate:
                candidates = uow.guests.probable_duplicates(guest)
                if candidates:
                    raise ProbableDuplicateError(candidates)
            guest = uow.guests.add(guest)
            record(
                uow,
                self._clock,
                actor,
                "guest.created",
                entity="guest",
                entity_id=guest.id,
                confirmed_duplicate=confirm_duplicate,
            )
            return guest

    def update(self, actor: Actor, guest_id: int, *, version: int, details: GuestDetails) -> Guest:
        """Correct contact details without touching the guest's history (scenario §4.1)."""
        require_staff(actor)
        details = details.cleaned()
        with self._uow() as uow:
            guest = self._load(uow, guest_id, version, for_change=True)
            changed = guest.apply(details)
            self._refuse_same_document(uow, guest)
            uow.guests.update(guest)
            # Field names only: the audit log never stores personal data.
            record(
                uow,
                self._clock,
                actor,
                "guest.updated",
                entity="guest",
                entity_id=guest.id,
                fields=changed,
            )
            return guest

    def set_flags(
        self,
        actor: Actor,
        guest_id: int,
        *,
        version: int,
        is_vip: bool,
        do_not_rent: bool,
        reason: str = "",
    ) -> Guest:
        """Any staff member marks VIPs; only a manager may set or clear do-not-rent."""
        require_staff(actor)
        reason = " ".join(reason.split())
        with self._uow() as uow:
            guest = self._load(uow, guest_id, version, for_change=True)
            if do_not_rent != guest.do_not_rent or (
                do_not_rent and reason != (guest.do_not_rent_reason or "")
            ):
                require_role(actor, Role.MANAGER)
            if do_not_rent and not 1 <= len(reason) <= MAX_REASON:
                raise ValidationError(
                    "guest.reason_required", fields={"reason": "guest.reason_required"}
                )
            guest.is_vip = is_vip
            guest.do_not_rent = do_not_rent
            guest.do_not_rent_reason = reason if do_not_rent else None
            uow.guests.update(guest)
            record(
                uow,
                self._clock,
                actor,
                "guest.flags_changed",
                entity="guest",
                entity_id=guest.id,
                vip=is_vip,
                do_not_rent=do_not_rent,
            )
            return guest

    def reveal_document(self, actor: Actor, guest_id: int) -> str:
        """Return the full identity document number, and record who looked at it."""
        require_staff(actor)
        with self._uow() as uow:
            guest = self._load(uow, guest_id)
            record(
                uow,
                self._clock,
                actor,
                "guest.document_revealed",
                entity="guest",
                entity_id=guest.id,
            )
            return guest.id_doc_number

    # ------------------------------------------------------------ helpers
    # ------------------------------------------------------------ anonymisation (5.7)
    def anonymisation_candidates(self, actor: Actor) -> tuple[date, list[Guest]]:
        """(cut-off date, guests with nothing since then and nothing booked)."""
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            cutoff = self._cutoff(uow)
            return cutoff, uow.guests.anonymisation_candidates(cutoff)

    def anonymise(self, actor: Actor, guest_ids: list[int]) -> int:
        """Erase the personal data of these guests; irreversible, audited.

        Eligibility is checked again here, inside the transaction: the list
        the manager saw may be out of date (a guest may have booked since).
        """
        require_role(actor, Role.MANAGER)
        now = self._clock.now()
        with self._uow() as uow:
            eligible = {g.id: g for g in uow.guests.anonymisation_candidates(self._cutoff(uow))}
            for guest_id in guest_ids:
                if guest_id not in eligible:
                    raise BusinessRuleViolation("guest.not_anonymisable")
            for guest_id in guest_ids:
                guest = eligible[guest_id]
                guest.anonymise(now)
                uow.guests.update(guest)
                uow.guests.mark_anonymised(guest)
                # Only the id is logged: the audit log must not keep what was erased.
                record(
                    uow, self._clock, actor, "guest.anonymised", entity="guest", entity_id=guest_id
                )
            return len(guest_ids)

    def _cutoff(self, uow: UnitOfWork) -> date:
        return months_before(self._clock.today(), load_settings(uow).anonymise_after_months)

    @staticmethod
    def _load(
        uow: UnitOfWork, guest_id: int, version: int | None = None, *, for_change: bool = False
    ) -> Guest:
        guest = uow.guests.get(guest_id)
        if guest is None or not guest.is_active:
            raise NotFoundError(entity="guest", id=guest_id)
        if version is not None and guest.version != version:
            raise StaleDataError(entity="guest", id=guest_id)
        if for_change and guest.is_anonymised:
            raise BusinessRuleViolation("guest.anonymised")
        return guest

    @staticmethod
    def _refuse_same_document(uow: UnitOfWork, guest: Guest) -> None:
        existing = uow.guests.find_by_document(guest.id_doc_type, guest.id_doc_number)
        if existing is not None and existing.id != guest.id:
            raise ConflictError(
                "guest.document_taken",
                fields={"id_doc_number": "guest.document_taken"},
                existing_id=existing.id,
            )
