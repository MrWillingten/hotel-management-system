"""Registering, finding and updating guests."""

from __future__ import annotations

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import ConflictError, NotFoundError, StaleDataError, ValidationError
from hotel.domain.guests import Guest, GuestDetails, IdDocType
from hotel.domain.paging import Page, PageRequest
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.authorization import require_role, require_staff

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
            guest = self._load(uow, guest_id, version)
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
            guest = self._load(uow, guest_id, version)
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
    @staticmethod
    def _load(uow: UnitOfWork, guest_id: int, version: int | None = None) -> Guest:
        guest = uow.guests.get(guest_id)
        if guest is None or not guest.is_active:
            raise NotFoundError(entity="guest", id=guest_id)
        if version is not None and guest.version != version:
            raise StaleDataError(entity="guest", id=guest_id)
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
