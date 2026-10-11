# Manual checks (story 6.6)

Automated tests cover the rules. These checks cover what only a person
sees: layout, keyboard use, printing, real browsers, a real Windows PC.
Run them on the release candidate before the feature freeze ends, and again
before the demo. Write the date and ✅ (passed), ❌ (failed, with a note) or ◐ (partly
checked, with what is left) in each cell.

## 1. Browsers

Use demo data: `python -m hotel seed --demo` in an empty data folder.

| # | Check | Chromium¹ | Firefox | Edge |
|---|---|---|---|---|
| B1 | Sign in, sign out; the back button after sign-out shows no guest data | | | |
| B2 | Two-factor: enrol by scanning the QR code with a real phone; sign in with a code; with a recovery code | ◐ 11 Oct: codes computed from the secret; phone and recovery code left | | |
| B3 | Book a stay (search → review → confirm); try to book the same room again → conflict with alternatives | | | |
| B4 | Change dates; cancel within 48 h → fee shown; check in; move to another room; check out → invoice | ◐ 11 Oct: move only | | |
| B5 | Bill: deposit, extra, discount (manager), refund; print the invoice (Ctrl+P) → only the document | | | |
| B6 | Reports: change the range, charts and tables agree; CSV opens in LibreOffice/Excel with accents intact | | | |
| B7 | Light, dark and system theme; every page readable in both | ◐ 11 Oct: dark theme only | | |
| B8 | Arabic: whole layout mirrored, numbers and codes readable, no horizontal scrolling | ✅ 11 Oct (sign-in, code page, move page, reservation) | | |
| B9 | French: no untranslated text on the pages above | | | |
| B10 | Width 360 px (phone) and 768 px (tablet): menu usable, tables scroll inside their box | | | |
| B11 | Keyboard only: Tab reaches every control, focus is visible, Enter submits | | | |
| B12 | Zoom 200 %: nothing overlaps or is cut off | | | |
| B13 | Browser console: no CSP violation and no error on the pages above | | | |

¹ The browser built into the development tool (Chromium engine), used by
the assistant while building Sprint 6. Firefox and Edge are checked by the
student on their own computer.

## 2. Real Windows PC (student)

Download `hotel.exe` (CI run → Artifacts → **hotel-windows**, or the
release). Use a Windows 10 or 11 PC **without Python installed**, ideally
one that has never run the program.

| # | Check | Result |
|---|---|---|
| W1 | SmartScreen shows "Windows protected your PC"; *More info → Run anyway* starts it (note the exact wording for the report) | |
| W2 | First start asks for the manager account in the black window; a weak password is refused with a clear reason | |
| W3 | The browser opens the sign-in page by itself; signing in works | |
| W4 | Data folder exists: `%LOCALAPPDATA%\HotelMedina` with `hotel.db`, `backups\`, `secret_key` | |
| W5 | Closing the black window stops the program (page no longer loads) | |
| W6 | Second start: no question asked, data still there, browser opens | |
| W7 | Arabic and French pages display correctly (fonts bundled, nothing missing offline) | |
| W8 | Unplug the network / Wi-Fi off: everything still works (fully offline) | |
| W9 | `hotel.exe backup` and `hotel.exe audit verify` in a Command Prompt | |
| W10 | Antivirus (Windows Defender): any warning? Note it for the report | |
| W11 | Time zone: the dashboard greeting and "today" match the PC's clock in Tunisia | |
| W12 | Two-factor sign-in with the student's real phone (Google Authenticator or similar) | |

## 3. Results and follow-up

Problems found here become GitHub issues with the label `bug`, are fixed
before the release, and are mentioned in the report's testing chapter.
