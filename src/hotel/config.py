"""Application settings, read from environment variables.

    HOTEL_ENV               production (default) | development | testing
    HOTEL_DATA_DIR          folder for the database and secret key (default: ./instance)
    HOTEL_NAME              name shown in the interface
    HOTEL_TIMEZONE          IANA time zone of the hotel (default: Africa/Tunis)
    HOTEL_HTTPS             1 when served over HTTPS (behind a TLS reverse proxy)
    HOTEL_TRUSTED_PROXIES   number of reverse proxies in front of the app (default: 0)

The default is *production*: forgetting to set the variable must never turn
the debugger on.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

ENVIRONMENTS = ("production", "development", "testing")
LANGUAGES = ("en", "fr", "ar")
RTL_LANGUAGES = frozenset({"ar"})


class ConfigurationError(RuntimeError):
    pass


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = "production"
    data_dir: Path = Path("instance")
    hotel_name: str = "Hotel Medina"
    timezone: str = "Africa/Tunis"
    https: bool = False
    trusted_proxies: int = 0
    scrypt_n: int = 2**15  # tests lower this to keep the suite fast

    def __post_init__(self) -> None:
        if self.environment not in ENVIRONMENTS:
            raise ConfigurationError(
                f"HOTEL_ENV must be one of {', '.join(ENVIRONMENTS)}, got {self.environment!r}"
            )
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError) as exc:
            raise ConfigurationError(f"Unknown time zone {self.timezone!r}") from exc
        if not 0 <= self.trusted_proxies <= 5:
            raise ConfigurationError("HOTEL_TRUSTED_PROXIES must be between 0 and 5")

    @property
    def debug(self) -> bool:
        return self.environment == "development"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "hotel.db"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def secret_key_path(self) -> Path:
        return self.data_dir / "secret_key"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None, *, environment: str | None = None
    ) -> Settings:
        env = os.environ if environ is None else environ
        try:
            trusted_proxies = int(env.get("HOTEL_TRUSTED_PROXIES", "0"))
        except ValueError as exc:
            raise ConfigurationError("HOTEL_TRUSTED_PROXIES must be a whole number") from exc
        return cls(
            environment=environment or env.get("HOTEL_ENV", "production").strip().lower(),
            data_dir=Path(env.get("HOTEL_DATA_DIR", "instance")).expanduser().resolve(),
            hotel_name=env.get("HOTEL_NAME", "Hotel Medina").strip() or "Hotel Medina",
            timezone=env.get("HOTEL_TIMEZONE", "Africa/Tunis").strip(),
            https=_flag(env.get("HOTEL_HTTPS")),
            trusted_proxies=trusted_proxies,
        )


def cli_command() -> str:
    """How to run the command-line tools here: the Windows build is one program (story 6.4)."""
    return "hotel.exe" if getattr(sys, "frozen", False) else "python -m hotel"
