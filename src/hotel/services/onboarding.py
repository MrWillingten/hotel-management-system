"""The walk-through for new accounts (story 6.14): tour state and checklist."""

from __future__ import annotations

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.errors import PermissionDeniedError
from hotel.domain.onboarding import Onboarding, ticked_keys
from hotel.persistence.unit_of_work import UnitOfWorkFactory


class OnboardingService:
    """Preferences of one's own account: not audited (nothing security-relevant)."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    def state(self, actor: Actor) -> Onboarding:
        user = self._user(actor)
        with self._uow() as uow:
            tour_done_at, dismissed_at = uow.onboarding.get(user.id)
            return Onboarding(
                is_manager=user.is_manager,
                tour_done=tour_done_at is not None,
                checklist_dismissed=dismissed_at is not None,
                done=ticked_keys(uow.audit.actions_of(user.id)),
            )

    def finish_tour(self, actor: Actor) -> None:
        """Finished or skipped: the welcome card disappears."""
        with self._uow() as uow:
            uow.onboarding.finish_tour(self._user(actor).id, self._clock.now())

    def dismiss_checklist(self, actor: Actor) -> None:
        with self._uow() as uow:
            uow.onboarding.dismiss_checklist(self._user(actor).id, self._clock.now())

    def restart(self, actor: Actor) -> None:
        """From the Help page: show the welcome card and the checklist again."""
        with self._uow() as uow:
            uow.onboarding.reset(self._user(actor).id)

    @staticmethod
    def _user(actor: Actor):
        if actor.user is None:
            raise PermissionDeniedError
        return actor.user
