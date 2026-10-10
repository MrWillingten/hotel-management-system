"""Splitting long lists into pages."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

MAX_PER_PAGE = 100


@dataclass(frozen=True, slots=True)
class PageRequest:
    page: int = 1
    per_page: int = 20

    def __post_init__(self) -> None:
        # Out-of-range values come from the URL, so they are corrected, not rejected.
        object.__setattr__(self, "page", max(1, self.page))
        object.__setattr__(self, "per_page", min(max(1, self.per_page), MAX_PER_PAGE))

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    items: Sequence[T]
    total: int
    request: PageRequest

    @property
    def page(self) -> int:
        return self.request.page

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.request.per_page))  # ceiling division

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages
