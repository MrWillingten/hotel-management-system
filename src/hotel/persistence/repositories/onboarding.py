from __future__ import annotations

from datetime import datetime

from hotel.persistence.convert import datetime_from_db, datetime_to_db
from hotel.persistence.repositories.base import BaseRepository


class OnboardingRepository(BaseRepository):
    def get(self, user_id: int) -> tuple[datetime | None, datetime | None]:
        """(tour finished or skipped at, checklist hidden at); (None, None) for a new user."""
        row = self._fetch_one(
            "SELECT tour_done_at, checklist_dismissed_at FROM onboarding WHERE user_id = ?",
            (user_id,),
        )
        if row is None:
            return None, None
        return datetime_from_db(row["tour_done_at"]), datetime_from_db(
            row["checklist_dismissed_at"]
        )

    def finish_tour(self, user_id: int, now: datetime) -> None:
        self._execute(
            "INSERT INTO onboarding (user_id, tour_done_at) VALUES (?, ?) "
            "ON CONFLICT (user_id) DO UPDATE SET tour_done_at = excluded.tour_done_at",
            (user_id, datetime_to_db(now)),
        )

    def dismiss_checklist(self, user_id: int, now: datetime) -> None:
        self._execute(
            "INSERT INTO onboarding (user_id, checklist_dismissed_at) VALUES (?, ?) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "checklist_dismissed_at = excluded.checklist_dismissed_at",
            (user_id, datetime_to_db(now)),
        )

    def reset(self, user_id: int) -> None:
        self._execute("DELETE FROM onboarding WHERE user_id = ?", (user_id,))
