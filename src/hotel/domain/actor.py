"""Who is performing an operation, and from where.

Every service method that changes data receives an Actor. It is used for role
checks and written into the audit log. The web layer builds it from the
signed-in user and the client address; the command line uses Actor.system().
"""

from __future__ import annotations

from dataclasses import dataclass

from hotel.domain.users import User


@dataclass(frozen=True, slots=True)
class Actor:
    user: User | None
    ip: str | None = None
    label: str = "system"  # describes a non-user actor ("cli", "anonymous"...)

    @classmethod
    def system(cls, label: str = "cli") -> Actor:
        """Someone with direct access to the server (command line)."""
        return cls(user=None, label=label)

    @property
    def is_system(self) -> bool:
        return self.user is None and self.label != "anonymous"

    @property
    def user_id(self) -> int | None:
        return self.user.id if self.user else None

    @property
    def username(self) -> str:
        return self.user.username if self.user else self.label
