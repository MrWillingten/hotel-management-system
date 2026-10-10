"""The key Flask uses to sign cookies and CSRF tokens.

Anyone who knows it can forge them, so it is never written in the source code
or committed to Git. It is generated randomly on first start and stored in the
data folder (which .gitignore excludes), readable only by its owner.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

MIN_KEY_LENGTH = 32


class WeakSecretKeyError(RuntimeError):
    pass


def load_or_create_secret_key(path: Path) -> str:
    if path.exists():
        key = path.read_text(encoding="utf-8").strip()
        if len(key) < MIN_KEY_LENGTH:
            raise WeakSecretKeyError(
                f"The secret key in {path} is too short. Delete the file to generate a new one."
            )
        return key

    key = secrets.token_hex(32)  # 256 bits
    path.parent.mkdir(parents=True, exist_ok=True)
    # O_EXCL: fail instead of overwriting if another process created it meanwhile.
    # 0o600: owner read/write only (ignored on Windows, where the user profile's
    # permissions apply instead).
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(key)
    return key
