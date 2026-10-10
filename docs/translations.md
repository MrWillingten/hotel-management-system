# Translations

The interface is available in English (source language), French and Arabic
(right-to-left). Translations use GNU gettext through Flask-Babel.

* In templates: `{{ _("Sign in") }}`, with parameters `{{ _("Welcome, %(name)s.", name=...) }}`.
* In Python: `gettext as _` inside a request, `lazy_gettext as _l` for module-level constants.
* Domain errors carry **codes**, translated in `src/hotel/web/messages.py`.

## Updating the catalogues after changing text

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
