# Translations

The interface is available in English (source language), French and Arabic
(right-to-left). Translations use GNU gettext through Flask-Babel.

* In templates: `{{ _("Sign in") }}`, with parameters `{{ _("Welcome, %(name)s.", name=...) }}`.
* In Python: `gettext as _` inside a request, `lazy_gettext as _l` for module-level constants.
* Domain errors carry **codes**, translated in `src/hotel/web/messages.py`.

## Updating the catalogues after changing text

The quickest way is the helper script, which extracts the strings, merges
them into both catalogues, optionally fills new ones from a JSON file
(`{"English text": ["French", "Arabic"]}`), compiles the `.mo` files and
lists anything still missing:

```bash
python scripts/i18n_sync.py new_strings.json
```

The same steps by hand:

Run from the project folder with the virtual environment active:

```bash
pybabel extract -F babel.cfg -k _l -k lazy_gettext --no-location --sort-output --project=hotel -o src/hotel/translations/messages.pot .
```

```bash
pybabel update -i src/hotel/translations/messages.pot -d src/hotel/translations --no-location
```

Edit `src/hotel/translations/fr/LC_MESSAGES/messages.po` and
`src/hotel/translations/ar/LC_MESSAGES/messages.po` (remove any `#, fuzzy` flag
once a translation is checked), then compile:

```bash
pybabel compile -d src/hotel/translations
```

`tests/e2e/test_translations.py` fails if a string is untranslated, a
placeholder such as `%(name)s` is lost, or the compiled `.mo` files are stale.

## Right-to-left rules

* `<html dir="rtl">` is set automatically for Arabic.
* CSS uses logical properties only (`margin-inline-start`, `inset-inline-end`,
  `border-inline-end`, `text-align: start`), so the layout mirrors by itself.
* Codes, amounts and identifiers that must stay left-to-right use `dir="ltr"`
  or `<bdi>`.
* Arabic uses Western digits (0–9), as is usual in Tunisia.

## Review status

The French and Arabic texts are first drafts and must be reviewed by a native
speaker before the final demo.

## Reviewing the translations (story 5.5)

The French and Arabic texts were drafted by AI and must be checked by a
native speaker before the demo.

```bash
python scripts/i18n_review.py export translations-review.csv
```

Open `translations-review.csv` in LibreOffice Calc or Excel (UTF-8,
comma-separated). Each row is one interface text: English, current French,
current Arabic. Write a better version in `french_correction` or
`arabic_correction` only where needed; leave the rest empty. Keep every
`%(name)s` marker exactly as in the English text (it is replaced by a value),
and write a percent sign as `%%`. Save as CSV, then:

```bash
python scripts/i18n_review.py import translations-review.csv
```

A correction with wrong markers is refused with the line number, and nothing
is changed until the whole file is correct. The review file is ignored by Git.
Arabic pages use Western digits (as Tunisian administration does), and every
amount is wrapped in `<bdi>` so it is never reordered inside right-to-left text.
