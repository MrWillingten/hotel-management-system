"""Translation catalogues must be complete and up to date.

If someone adds `_("New text")` without updating the French and Arabic
catalogues, these tests fail (see docs/translations.md for the commands).
"""

import io
import subprocess
import sys
from pathlib import Path

import pytest
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

ROOT = Path(__file__).resolve().parents[2]
TRANSLATIONS = ROOT / "src" / "hotel" / "translations"
LANGUAGES = ("fr", "ar")


def _catalog(language):
    with open(TRANSLATIONS / language / "LC_MESSAGES" / "messages.po", "rb") as handle:
        return read_po(handle, locale=language)


@pytest.fixture(scope="module")
def source_message_ids(tmp_path_factory):
    pot = tmp_path_factory.mktemp("i18n") / "messages.pot"
    subprocess.run(  # noqa: S603 - fixed arguments, no user input
        [
            sys.executable,
            "-m",
            "babel.messages.frontend",
            "extract",
            "-F",
            "babel.cfg",
            "-k",
            "_l",
            "-k",
            "lazy_gettext",
            "--no-location",
            "-o",
            str(pot),
            ".",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    with open(pot, "rb") as handle:
        return {m.id for m in read_po(handle) if m.id}


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_source_string_is_translated(language, source_message_ids):
    catalog = _catalog(language)
    translated = {m.id for m in catalog if m.id and m.string and not m.fuzzy}
    missing = sorted(source_message_ids - translated)
    assert not missing, f"{language}: untranslated strings: {missing}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_placeholders_are_kept(language):
    for message in _catalog(language):
        if message.id:
            for placeholder in (
                "%(name)s",
                "%(greeting)s",
                "%(id)s",
                "%(count)s",
                "%(page)s",
                "%(pages)s",
                "%(username)s",
                "%(number)s",
                "%(max)s",
                "%(first)s",
                "%(last)s",
                "%(reopens)s",
                "%(total)s",
                "%(query)s",
                "%(adults)s",
                "%(children)s",
                "%(nights)s",
                "%(when)s",
                "%(code)s",
                "%(room)s",
                "%(capacity)s",
                "%(occupants)s",
                "%(fee)s",
                "%(tz)s",
                "%(minutes)s",
                "%(min_length)s",
                "%(max_length)s",
            ):
                assert (placeholder in message.id) == (placeholder in message.string), message.id


@pytest.mark.parametrize("language", LANGUAGES)
def test_compiled_files_match_the_sources(language):
    expected = io.BytesIO()
    write_mo(expected, _catalog(language))
    compiled = (TRANSLATIONS / language / "LC_MESSAGES" / "messages.mo").read_bytes()
    assert compiled == expected.getvalue(), (
        f"Run: pybabel compile -d {TRANSLATIONS.relative_to(ROOT)}"
    )
