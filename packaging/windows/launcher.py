"""Entry point of the Windows executable (story 6.4).

Double-clicking hotel.exe should "just work" for someone who has never
installed Python:

* data goes to %LOCALAPPDATA%\\HotelMedina, which is always writable (the
  program itself may sit in a read-only folder such as Program Files);
* on the very first start, the console asks for the first manager account;
* then the server starts and the browser opens the sign-in page.

With arguments it behaves exactly like `python -m hotel ...`, for example
`hotel.exe backup` or `hotel.exe reset-password mona`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _default_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "HotelMedina"


def main() -> int:
    os.environ.setdefault("HOTEL_DATA_DIR", str(_default_data_dir()))

    from hotel.bootstrap import build_services
    from hotel.cli import main as cli_main
    from hotel.config import Settings

    if sys.argv[1:]:
        return cli_main(sys.argv[1:])

    print(f"Data folder: {os.environ['HOTEL_DATA_DIR']}")
    if not build_services(Settings.from_env()).auth.has_users():
        print("First start: create the manager account.")
        if cli_main(["create-manager"]) != 0:
            input("Press Enter to close this window.")
            return 1
    code = cli_main(["run", "--open-browser"])
    if code:
        # Double-clicked windows close at once: keep the error readable.
        input("Press Enter to close this window.")
    return code


if __name__ == "__main__":
    sys.exit(main())
