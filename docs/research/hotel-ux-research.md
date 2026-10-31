# How hotel PMS software is designed and used: research and recommendations

*Written 31 Oct 2026, in reply to the Web Development professor's review
(upgrades, better layout, UX based on how receptionists and managers really
work). Research only: nothing in the code was changed.*

**How to read it.** Each claim cites a source in square brackets, e.g. [S3],
and the [Sources](#sources) list at the end gives the URLs. Text marked
**Judgement:** is the author's own reasoning, not a sourced fact. Many PMS
sources are vendor documentation or vendor blogs: they show what products
*do*, which is not independent proof that it works. Review sites (Capterra,
G2) are short, unverified opinions. The only academic sources are the
interruption research and one dissertation.

**Constraints applied to every recommendation.** No JavaScript (strict
CSP); each change must be something the student can explain; the demo is
on 14 Dec 2026 and CP4 (integration) is on 30 Nov, so cost matters.
Cost: **S** ≈ under half a day (template + small service change + tests),
**M** ≈ 1 to 2 days, **L** ≈ more than 2 days or a new migration with a
whole new area. Priority uses MoSCoW (Must / Should / Could / Won't for
now).

---

## Contents

1. [How PMS products are organised](#1-how-pms-products-are-organised)
2. [What the research says about the people](#2-what-the-research-says-about-the-people)
3. [Receptionist: findings and recommendations](#3-receptionist-findings-and-recommendations)
4. [Manager: findings and recommendations](#4-manager-findings-and-recommendations)
5. [Layout and navigation changes](#5-layout-and-navigation-changes)
6. [Quick wins](#6-quick-wins)
7. [What the app already does well](#7-what-the-app-already-does-well)
8. [Suggested order before the freeze](#8-suggested-order-before-the-freeze)
9. [Sources](#sources)

---

## 1. How PMS products are organised

Across the products studied, the same building blocks appear, under
different names.

| Building block | What it is | Examples |
|---|---|---|
| **Today / front-desk overview** | One screen with the day's arrivals, departures, stay-overs and in-house guests, each with an action. | Mews *Reservation overview* with tabs Arrivals, Departures, Stay overs, Staying, Statistics [S1]; Cloudbeds dashboard with Arrivals, Departures and In-house widgets and a "rooms left to check out" count [S2]; protel Air opens on an "active desktop" whose top list is today's arrivals [S3]; OPERA Cloud *Front Desk Workspace* with Arrivals, In-house, Queue, Room Assignment [S4][S5]. |
| **Tape chart / timeline / room rack** | Rooms down the side, dates across, each stay a bar; the "what is free when" view. | Mews *Timeline* grouped by category then room, with density, time-unit and floor/feature filters [S6]; Hotelogix tape chart where room colour = housekeeping state and each cell = one room-night [S7]; protel *room plan* and *room type plan* (F2) [S3]; Cloudbeds calendar with filters that grey out non-matching stays and per-role calendar settings [S8]. |
| **Status colour language** | One colour per *urgency*, not just per state. | Mews: orange = urgent (no-show, missed check-in/out), blue = action due today, dark grey = in house, nothing to do, light grey = not today; housekeeping red/yellow/orange/blue/green; icons for returning guest, VIP class, group, "do not move" lock [S6]. |
| **Housekeeping board** | Every room with its cleaning state and front-office state; bulk updates; discrepancies. | OPERA: statuses Inspected, Clean, Pickup, Dirty, Out of Service, Out of Order; select several rooms and update at once; *Sleep/Skip* discrepancies when housekeeping and front office disagree [S9][S10]. |
| **Reservation alerts and traces** | Notes that *pop up at the right moment* (check-in, check-out) and to-dos for a department with a due time. | OPERA reservation alerts (shown at check-in/check-out, with a warning icon and count) and traces (department + due date/time, open by default) [S11][S12]. |
| **Guest profile** | Identity, stay history, preferences, notes; recognition at check-in. | OPERA tour: icons for VIP, first-time or repeat guest [S13]; Mews users ask for a "how many times stayed" counter [S14]; preferences (recurring, alert-worthy) vs notes (one-off) [S15]. |
| **Night audit / end of day** | Close the business day, after a **pre-audit checklist** of exceptions. | Visual Matrix pre-audit checklist: guests due out, no-shows, pre room-and-tax report, cashier close [S16]; Prostay advises testing that the audit *stops* on an open problem rather than carrying it silently [S17]. |
| **Reports and BI** | Daily manager report (day / month-to-date / year-to-date), occupancy, ADR, RevPAR, pickup and pace. | Mews checklist: management reviews the Manager report (previous day, MTD, YTD) and occupancy by room type [S18]; Mews BI *Pickup* dashboard [S19]. |

The **daily rhythm** these screens serve is spelled out in Mews' suggested
operations checklist [S18]: the morning shift reviews arrivals and
departures (notes, rates, room allocation), checks open balances of
guests in house, follows up on pending tasks and hands the cash over; the
afternoon shift makes sure every remaining arrival has an *inspected*
room and checks tomorrow's arrivals; the night shift resolves no-shows,
prepares bills for early departures and checks that revenue was posted.
OPERA's assistant only allows check-in when a room is assigned and clean
or inspected, and only checks out at a zero balance [S5].

**Judgement:** this app already has most of the building blocks (dashboard,
availability grid, housekeeping states, alerts on the reservation page,
night audit, reports). What real products add on top is mainly
*information density at the point of action*: the arrivals row tells you
whether the room is ready, whether the guest is a VIP or a regular,
whether money is owed, and whether there is a note, so the receptionist
never has to open the record to find out.

---

## 2. What the research says about the people

### Front desk: time pressure, interruptions, phone in hand

* **Interruptions hurt, and intensity matters more than frequency.** An
  Auburn University thesis on hotel front-office staff found that
  interruptions (from guests, colleagues, managers and technology) raise
  mental strain, which lowers speed, accuracy and service quality; the
  intensity of interruptions mattered more than how often they came, and
  technology-related interruptions stood out [S20].
* **Resuming after an interruption costs time; visible cues shorten it.**
  The "memory for goals" research (Altmann and Trafton) measures a
  *resumption lag* after every interruption and shows that cues in the
  environment that show what you were doing, or what comes next, speed
  up resumption [S21][S22].
  **Judgement:** for a web app without JavaScript, the best cues are
  URLs that keep their state (filters and steps in the query string, which
  this app already does), page titles that say which reservation is
  open, and step numbers in multi-step forms.
* **Multitasking is the norm.** Front-desk clerks often cover reservations,
  concierge and telephone at once [S23].
* **Staff learn on the job, fast.** Cloudbeds' survey with NYU Tisch Center
  (500 hotel employees, 5 countries; vendor-funded) reports that 85 %
  get two weeks or less of PMS training, managers think confidence takes
  4 months to 3 years, staff rate the PMS lower on *reducing mistakes*
  than on usefulness, and 38 % say the PMS played a part in leaving a
  job [S24][S25]. Managers named a confusing, overwhelming interface,
  wrong or incomplete data entry, not knowing the easiest way, and
  getting stuck on errors while the guest waits [S24].
* **The human part of the encounter matters most.** Interviews with 30
  receptionists found that IT carries the *tasks*, but in critical service
  incidents the human presence is what counts and IT rarely helps [S26].
  **Judgement:** the screen should let the receptionist look up from it
  quickly: short, glanceable rows rather than long forms.

### Usability principles that apply directly

* **Recognition rather than recall** (Nielsen heuristic 6): showing options
  is easier than making people remember them; search suggestions turn
  recall into recognition [S27].
* **Flexibility and efficiency** (heuristic 7): accelerators for frequent
  tasks that experts use and beginners can ignore [S28]. OPERA Cloud shows
  its shortcut keys on screen when Ctrl is held [S29]; protel opens its
  room-type plan with F2 [S3].
* **Error prevention:** slips (autopilot, wrong button) are prevented by
  constraints, good defaults and distance between consequential
  actions; confirmation dialogs help only when they are rare, otherwise
  people click through them [S30][S31].
* **Colour is never the only signal** (WCAG 1.4.1, level A): add a shape,
  pattern or text [S32].
* **Dashboards:** use length and position (bars) for numbers, not colour,
  pies or gauges; an *operational* dashboard should be readable on one
  screen and tell you what to do now [S33].

### Managers: exceptions and trends

* KPI guides converge on a headline strip (occupancy, ADR, RevPAR) plus a
  separate **forward-looking** band (on-the-books, pickup, pace for the
  next ~30 days), because RevPAR only tells what already happened
  [S34][S35]. Showing occupancy and ADR next to RevPAR tells which of the
  two moved [S34].
* **Exception-first:** night-audit guidance says to isolate exceptions
  (what blocks closing vs what can wait) instead of re-checking
  everything, and to record who reviewed what [S36][S16].
* Mews' checklist has managers look every morning at yesterday's special
  requests, missing payments and failed payments, the no-show list, and
  the manager report [S18].

### What reviews praise and complain about

* Complaints that recur: **too many clicks** (Clock PMS, Hotello: "lots of
  clicks and very small printing") [S37][S38], a steep **learning curve**
  (Hotelogix, Maestro) [S39], dependence on the internet connection
  (OPERA Cloud) [S40], slow or crashing systems [S38].
* Praise that recurs: an easy, intuitive **calendar** (Cloudbeds' calendar
  scores 9.5 on G2's feature breakdown) [S41], **ease of learning** (Mews
  rated 4.7 for ease of use on Capterra) [S42], and a night audit that is
  easy to run (Clock PMS) [S37].
* Users of Mews ask for **more colour coding and icons** on the timeline
  (payment status, source, VIP, group) so that they do not have to open
  each booking [S43][S44], and for consistent room names and custom room
  order [S45].

---

## 3. Receptionist: findings and recommendations

What exists today (from `docs/user-guide.md` and the templates): the
dashboard (`dashboard/index.html`) shows six stat cards, then Arrivals and
Departures lists (name, code, rooms, "Late"/"Overdue", one button), then
"Unpaid after departure" and Housekeeping. The arrival row does **not**
show whether the room is ready, whether the guest is VIP or returning,
whether there is a note, or what is owed. The availability grid
(`availability/index.html`) shows 14 nights, colours for Reserved and
Occupied, and the guest's surname on the first night. New reservations
are a three-step page (`reservations/new.html`).

### R1. Arrivals rows that answer the four questions at a glance

* **What:** in each arrival row on the dashboard add (a) the room's
  housekeeping state with the existing `housekeeping_badge` ("Ready",
  "To clean", "To inspect"); (b) the VIP flag with the existing
  `flags(guest)` macro and a "Returning: 3 stays" badge; (c) a note icon
  plus the first ~60 characters of the reservation note; (d) "Deposit
  paid: …" or "Nothing paid yet". Sort rows so that *ready* rooms come
  first (they can be checked in now).
* **Why:** Mews' checklist makes "do the remaining arrivals have inspected
  rooms?" an explicit task of every shift [S18], OPERA refuses check-in
  if the room is not clean/inspected [S5], and both Mews and OPERA show
  VIP and repeat-guest icons on the arrival/timeline row [S6][S13]. It
  turns four recalls (or four clicks) into recognition [S27] and
  removes the "open each booking" complaint [S43]. This app already
  warns about unready rooms, but only *after* opening the reservation.
* **Where:** `services/front_desk.py` (`FrontDeskDay`: add a
  per-arrival view with room readiness, flags, stay count, paid amount;
  rooms and `bill_for` are already loaded there), `dashboard/index.html`,
  CSS `.pick-list`.
* **Cost:** S to M. **Needs JS:** no. **Priority:** **Must**.

### R2. Departures rows that show the balance

* **What:** each departure shows "Balance due 340,000 DT" (warning badge)
  or "Paid" (with a check icon). Optionally sort unpaid ones first.
* **Why:** checkout at a zero balance is the norm in OPERA [S5];
  Mews' night shift prepares bills for early departures the evening
  before [S18]. Seeing the amount while the guest walks up lets the
  receptionist prepare the payment rather than discover it on the
  check-out page. The total "Due from guests in the house" is already
  computed in the same loop.
* **Where:** `services/front_desk.py`, `dashboard/index.html`.
* **Cost:** S. **Needs JS:** no. **Priority:** **Must**.

### R3. An "In house" list

* **What:** a third list (or a `?tab=in-house` page) of guests currently
  staying: room, name, departure date, balance, VIP. Make the "Guests in
  the house" card a link to it, like the Arrivals and Departures cards.
* **Why:** every product studied has an in-house / "Staying" view next to
  arrivals and departures [S1][S2][S4]; the in-house open-balance check is
  a task of all three shifts in Mews [S18]. Today the card is the only
  stat card that leads nowhere.
* **Where:** `dashboard/index.html` (data is already in `day.in_house`).
* **Cost:** S. **Needs JS:** no. **Priority:** **Should**.

### R4. One search box in the top bar

* **What:** a GET form in `layouts/app.html` ("Code, guest or room").
  A reservation code opens that reservation; a room number opens the room
  (or its current reservation); anything else goes to the guest search
  results with their reservations. Optional `accesskey="k"` (see R12).
* **Why:** the phone rings in the middle of another task: the guest says a
  name, a room number or a code. One box that accepts all three is
  recognition rather than recall (no need to remember *which* page
  searches what) [S27] and shortens the detour, which matters because
  every interruption has a resumption cost [S21][S20]. Mews has a
  timeline search on category names and room numbers [S6].
* **Where:** `layouts/app.html`, a small `search` route that redirects
  (reuses `reservations` and `guests` repository searches).
* **Cost:** S to M. **Needs JS:** no (plain GET form and a redirect).
  **Priority:** **Must**.

### R5. Quote the full price while on the phone

* **What:** in step 3 of New reservation, add a column "Stay total
  (before tax)" = sum of the nightly prices for the chosen dates, and
  show "Nights: 3" above the table. Default the dates to today → tomorrow
  when empty.
* **Why:** a walk-in or caller asks "how much for three nights?"; the
  walk-in SOPs put "quote the rate, confirm the total" before creating the
  booking [S46]. Today the total appears only on the review page, after a
  guest has been chosen. Prices vary per night (seasonal, weekend), so the
  nightly rate alone can mislead.
* **Where:** `reservations/new.html`, the service that lists free rooms
  (pricing already exists in `domain/pricing.py`).
* **Cost:** S. **Needs JS:** no. **Priority:** **Must**.

### R6. Walk-in in one flow

* **What:** a "Walk-in" button next to "New reservation" on the dashboard:
  it opens New reservation with today → tomorrow and, after **Confirm
  booking**, offers **Check in now** directly on the confirmation (only
  if the room is ready).
* **Why:** the walk-in procedure is: check for an existing booking, check
  same-day availability, quote, create, assign, check in [S46]; joining
  the last two steps removes a page and a search. Sabre's walk-in screen
  forces arrival = today [S46].
* **Where:** `dashboard/index.html`, `reservations/review.html` (or the
  page shown after confirming).
* **Cost:** S to M. **Needs JS:** no. **Priority:** **Should**.

### R7. Availability grid that reads without colour and filters by category

* **What:** (a) add a *pattern or letter* to Reserved vs Occupied (e.g. a
  left border and "●" for in-house, an outline for reserved), because
  today they differ by colour only; (b) a category filter and "4 weeks"
  option; (c) colour the room number cell with its housekeeping state
  (as Mews does) and mark arrival-day cells with a small "→" and
  departure-day with "←"; (d) a VIP star on the first cell.
* **Why:** WCAG 1.4.1 forbids colour as the only signal [S32] and the app's
  own requirements promise WCAG AA; Mews colours room numbers by
  housekeeping state and uses icons for returning guests and VIPs [S6];
  Cloudbeds lets staff filter so that non-matching stays are greyed out
  [S8]; Mews users ask for exactly this kind of at-a-glance coding [S43].
  The calendar is the feature reviewers praise most when it works well
  [S41].
* **Where:** `availability/index.html`, `app.css` (`.cell--*`),
  availability service (category filter).
* **Cost:** S for (a) and (c), S to M for (b) and (d). **Needs JS:** no
  (drag-and-drop booking, as in Cloudbeds or Hotelogix [S7], *would* need
  JS; the no-JS equivalent already exists: click a free cell to start a
  booking). **Priority:** **Must** for (a), **Should** for the rest.

### R8. A housekeeping board that puts today's arrivals first

* **What:** a "Housekeeping" view (a filter on Rooms, or its own page)
  grouped by state: *To clean*, *To inspect*, *Ready*, with a tag
  "Arrival today" / "Departure today" / "Stay-over" on each room, sorted
  so that rooms with an arrival today come first. Checkboxes and one
  "Mark cleaned" button for several rooms at once (an ordinary form with
  several checkboxes). Large touch targets so a housekeeper can use a
  phone.
* **Why:** OPERA's board updates several rooms at once and lets
  supervisors prioritise rooms [S9]; RoomRaccoon's housekeeping forecast
  shows arrivals, stay-overs and check-outs per room [S47]; the
  front-desk/housekeeping hand-off is where rooms get sold while not
  ready [S48]. **Judgement:** sorting by "arrival today" is the single
  change that most reduces "room not ready" moments at the desk.
* **Where:** `rooms/index.html` or a new `housekeeping` template; a small
  service method that joins rooms with today's arrivals/departures; one
  POST route for the bulk update (each room still goes through the
  existing domain rule).
* **Cost:** M. **Needs JS:** no. **Priority:** **Should**.

### R9. Alerts that appear at check-in, not only on the record

* **What:** a tick box "Show at check-in" on the reservation note (or a
  separate short "Alert" field). If set, the arrival row shows a warning
  icon and the check-in result page/flash repeats the text ("Collect
  passport copy", "Birthday: cake in room").
* **Why:** OPERA's reservation alerts fire at check-in and check-out and
  show a count icon [S11]; recurring *preferences* should drive alerts,
  one-off notes should not, otherwise staff are flooded [S15].
* **Where:** migration (one column), `reservations/new.html` and
  `edit.html`, dashboard row, check-in flash.
* **Cost:** M (migration + forms + tests). **Needs JS:** no.
  **Priority:** **Could** (R1's note preview gives most of the value for
  S).

### R10. A shift log for handover

* **What:** a "Desk log" page: short entries with author and time, an
  optional link to a reservation or room, and **Mark done**; open entries
  are listed on the dashboard ("Open handover items: 2").
* **Why:** OPERA's traces send dated to-dos to a department and stay open
  until resolved [S12]; handover guidance says the point is transferring
  *responsibility* (owner, next action, deadline), not memory, and that
  paper logs lose items [S48][S49] (vendor sources, treat numbers with
  care). Interruptions make it likely a promise made on the phone gets
  forgotten [S20].
* **Where:** new table + migration, a small service and blueprint, a
  dashboard panel; every entry audited like other actions.
* **Cost:** M to L. **Needs JS:** no. **Priority:** **Could** (good demo
  story, but new code area; do it only after the Musts).

### R11. Make slips less likely and their result obvious

* **What:** (a) put the room number in the dashboard button label
  ("Check in · 204") so the wrong row is noticed; (b) after check-in or
  check-out, the flash names the guest and room ("Amira Ben Ali is
  checked in, room 204"); (c) on the reservation page, keep **one**
  primary button per status (Check in *or* Check out) and turn **Change**
  into a secondary button; (d) move **Cancel reservation** and **Record a
  no-show** away from the everyday buttons, to a separate block at the
  bottom ("Other actions").
* **Why:** slips happen on autopilot; prevention is constraints, clear
  labels and keeping consequential actions apart from benign ones
  [S30][S31]. Confirmation pages help only when rare [S31]: the app already
  uses them for the costly ones (cancel, no-show, check-out), which is
  right. Managers in the Cloudbeds study describe staff "clicking icons
  without thinking" under pressure [S24].
* **Where:** `dashboard/index.html`, `reservations/detail.html`,
  check-in/check-out flash messages, `app.css`.
* **Cost:** S. **Needs JS:** no. **Priority:** **Must** (cheap, and it is
  exactly the professor's "psychology" point).

### R12. Keyboard: focus where the work starts

* **What:** `autofocus` on the first useful field of task pages (step 1
  of New reservation, reservations search, payment amount on the bill);
  `accesskey` on the top-bar search and "New reservation", listed on the
  Help page. Keep the existing skip link and visible focus.
* **Why:** accelerators for frequent tasks that beginners can ignore
  [S28]; OPERA and protel give experts keys for the commonest screens
  [S29][S3]. **Judgement:** `accesskey` is pure HTML (no JS) but its
  modifier differs per browser (Alt, Alt+Shift, Ctrl+Option) and it can
  clash with screen-reader keys, so use at most two and document them;
  real custom shortcuts like OPERA's Ctrl overlay would need JavaScript
  and are therefore out of scope.
* **Where:** `macros/forms.html` (already supports `autofocus`),
  `layouts/app.html`, `help/index.html` / `web/help.py`.
* **Cost:** S. **Needs JS:** no (custom key handling would; not
  recommended). **Priority:** **Should**.

### R13. "Last updated" instead of auto-refresh

* **What:** show "Updated 14:32 · Refresh" at the top of the dashboard and
  availability grid.
* **Why:** the dashboard is a snapshot; two receptionists working at
  once can act on stale lists. **Judgement:** a `<meta http-equiv=
  "refresh">` would work without JS, but it would throw away half-typed
  input and moves content under the user, which conflicts with WCAG
  2.2.1 (timing adjustable); a visible time and a link are safer. The
  app already handles concurrent edits with version checks.
* **Where:** `dashboard/index.html`, `availability/index.html`.
* **Cost:** S. **Needs JS:** no. **Priority:** **Could**.

### R14. Printable day sheets

* **What:** a print style for the dashboard lists (arrivals, departures,
  housekeeping) so the morning shift can print the day (Ctrl+P), like the
  invoice already does.
* **Why:** Mews' checklist prints registration cards and exports the space
  status report to split housekeeping work [S18]; a paper list is also the
  fallback when the computer is busy or down. **Judgement:** cheap with
  the existing `@media print` rules.
* **Where:** `app.css` print section, `no-print` classes on the dashboard.
* **Cost:** S. **Needs JS:** no. **Priority:** **Could**.

---

## 4. Manager: findings and recommendations

What exists today: managers see the *same* dashboard as receptionists,
plus an Administration menu. Reports (`reports/index.html`) need three
dates and **Show** before anything appears; they cover occupancy, ADR,
RevPAR, invoiced, cash, cancellations, categories, availability on one
day, outstanding balances, CSV export and bar charts. Night audit
(`night_audit/index.html`) closes a day and shows what happened *after*
closing.

### M1. "Needs attention" panel (exception-first)

* **What:** at the top of the dashboard, a short list that appears only
  when something is wrong, each line a link: overdue departures; arrivals
  past the check-in time not yet checked in; rooms needed today that are
  not ready; in-house balances above a threshold; unpaid invoices older
  than N days; for managers also: yesterday not closed by the night audit,
  last backup older than one day, audit chain broken, two-factor not set
  up. When nothing is wrong: "Nothing needs attention."
* **Why:** managers scan for exceptions; night-audit guidance separates
  blocking from non-blocking issues and wants them reviewed before the
  next shift [S36][S16]; Mews' manager routine starts with failed or
  missing payments and no-shows [S18]; Mews' colour language reserves
  orange for "urgent" (no-shows, missed check-in/out) [S6]. Everything
  listed is already computed somewhere in the app (dashboard, night
  audit, backups, audit verify).
* **Where:** `services/front_desk.py` (or a small `services/attention.py`),
  `dashboard/index.html`.
* **Cost:** M (S for the front-desk items alone). **Needs JS:** no.
  **Priority:** **Must**.

### M2. Forward look: the next 14 to 30 days on the books

* **What:** a manager-only strip or Reports section "On the books": for
  each of the next 14 (or 30) nights, rooms sold / sellable as a
  horizontal bar, ADR on the books, and **pickup** = nights booked in the
  last 7 days (from `reservation.created_at`) minus cancellations.
* **Why:** KPI guides separate *history* (RevPAR, ADR) from the *forward
  look* (on-the-books, pickup, pace), because RevPAR only says what
  already happened [S34][S35]; pickup is new bookings since the last check,
  and net pickup can hide cancellations, so show both [S34]. Mews has a
  dedicated pickup dashboard [S19]. Bars, not pies or gauges [S33]. The
  `room_night` table makes "nights sold per future date" one query.
* **Where:** `repositories/reports.py`, `services/reports.py`, new block in
  `reports/index.html` (and a smaller version on the manager dashboard);
  reuse `macros/charts.html`.
* **Cost:** M. **Needs JS:** no (bars are already CSS/SVG). **Priority:**
  **Should**.

### M3. Report presets and comparison

* **What:** (a) links above the date fields: *Yesterday*, *This month*,
  *Last month*, *Next 30 days*, *Year to date*; open Reports on "This month"
  by default instead of an empty page; (b) a "same period last year"
  column with the difference for occupancy, ADR, RevPAR and revenue.
* **Why:** Mews' manager report shows day, month-to-date and
  year-to-date [S18]; dashboards should compare with last year (or a
  budget, since a weak last year flatters) and show which driver moved
  [S34]. Presets are recognition instead of typing six dates [S27].
* **Where:** `reports/index.html`, `web/blueprints/reports.py`; (b) also
  `services/reports.py` (run the same report twice).
* **Cost:** S for (a), M for (b). **Needs JS:** no. **Priority:** (a)
  **Must** (quick win), (b) **Could**.

### M4. Night audit: preview before closing

* **What:** show, *before* the **Close the day** button, what will happen:
  arrivals that will become no-shows, guests still in after departure,
  balances still open, and the figures that will be frozen. The button
  stays; the preview is a GET of the same data.
* **Why:** every pre-audit checklist found starts with guests due out and
  no-shows and makes the auditor confirm them [S16][S36]; Prostay
  suggests checking whether the audit blocks on errors or carries them
  silently [S17]. Today the manager learns the no-shows after they are
  recorded. **Judgement:** keep it non-blocking (the app runs missed
  audits automatically at start-up), but make the consequences visible
  first, exactly as the cancel page already shows the fee before
  confirming.
* **Where:** `services/night_audit.py` (a dry-run that returns the
  outcome without writing), `night_audit/index.html`.
* **Cost:** S to M. **Needs JS:** no. **Priority:** **Should**.

### M5. Audit log "sensitive actions" view

* **What:** a preset filter on the audit log for refunds, discounts,
  voids, tax exemptions, document reveals, staff changes and exports,
  newest first; plus a count on the manager dashboard ("3 refunds this
  week").
* **Why:** exception-first review and "who reviewed what" [S36]; managers
  check rebates/posting journals daily in Mews' checklist [S18].
* **Where:** `audit/index.html`, the audit blueprint (fixed whitelist of
  actions, as the SQL rules require).
* **Cost:** S. **Needs JS:** no. **Priority:** **Should**.

### M6. Price calendar for checking rates

* **What:** read-only grid: categories down, nights across (4 weeks),
  each cell the price that a booking made *now* would get (seasonal rate,
  weekend surcharge, base price), with the rule that produced it in the
  cell title.
* **Why:** rate/availability calendars are a standard PMS screen [S8][S3];
  the app has a pricing order (rate period → weekend → room price) that a
  manager can only check today by starting fake bookings. **Judgement:**
  also a strong demo/explanation aid for the pricing rules.
* **Where:** `domain/pricing.py` (already computes it), new template under
  `rooms/` next to **Seasonal rates**.
* **Cost:** M. **Needs JS:** no. **Priority:** **Could**.

### M7. Settings that explain their effect

* **What:** under the cancellation settings, a worked example computed
  from the current values ("A 3-night stay at 540 DT cancelled 24 h before
  arrival costs 108 DT"); same for weekend surcharge.
* **Why:** configuration mistakes are mistakes of the mental model, which
  are prevented by showing consequences [S30]. **Judgement:** small, and
  it doubles as the professor-facing explanation of BR11.
* **Where:** `settings/index.html`, `web/blueprints/hotel_settings.py`.
* **Cost:** S. **Needs JS:** no. **Priority:** **Could**.

### Not recommended before the demo (Won't, with reason)

* **Drag-and-drop tape chart, live updates, charts with hover tooltips:**
  need JavaScript. The no-JS equivalents (click a cell, Refresh link,
  values printed next to bars) already exist or are proposed above.
* **Group bookings / blocks, channel manager, online check-in, rate
  plans:** large features from multi-property or OTA-connected products
  (OPERA blocks, Mews optional bookings [S6][S12]); out of scope for a
  single-hotel staff tool and too costly before 14 Dec.
* **Room-type booking with later room assignment** (OPERA/protel
  model [S3][S4]): the app assigns a room at booking, which is simpler and
  matches small hotels; changing it touches the core rule set (ADR 0004).

---

## 5. Layout and navigation changes

| # | Change | Why | Where | Cost | JS | Priority |
|---|---|---|---|---|---|---|
| L1 | **Dashboard order by role.** Receptionist: Needs attention → Arrivals / Departures (side by side) → In house → Housekeeping; the six stat cards become one compact strip. Manager: Needs attention → stat strip with forward look → lists. | Operational dashboards should show "what to do now" on one screen [S33]; Mews' overview is organised by today's actions [S1]. Today the lists start below six large cards. | `dashboard/index.html`, `app.css` | S–M | no | Should |
| L2 | **Top bar: search + "New reservation" on every page.** | Most frequent tasks always one click away [S28]; phone interruptions [S20]. | `layouts/app.html` | S | no | Must (with R4) |
| L3 | **Sidebar groups:** "Front desk" (Dashboard, Availability, Reservations, Guests), "House" (Rooms / Housekeeping), "Money" (Invoices), then Administration; Help at the bottom near the version. | Group by task, not by data type (Judgement); frequent items first. | `layouts/app.html` | S | no | Should |
| L4 | **Unique icons.** Reports and Availability both use "grid"; Invoices and Backups both use "archive". | Icons only help recognition if they are distinct [S27][S32]. | `layouts/app.html`, `macros/icons.html` | S | no | Should |
| L5 | **Every stat card leads to its list**, and to the *right* list: "Due from guests in the house" currently jumps to "Unpaid after departure", which is a different set of people; "Guests in the house" and "Occupancy" are not links. | Consistency; the mismatch can mislead a receptionist chasing money. | `dashboard/index.html` | S | no | Must |
| L6 | **One primary button per page** (the next step in the lifecycle), others secondary; destructive actions in a separate block. | Clarity of the next action; distance between consequential options [S31]. | `reservations/detail.html`, bill page | S | no | Must (with R11) |
| L7 | **Move the version/schema/time-zone footer** from the dashboard to Help or the sidebar footer (which already shows the version). | Removes noise from the busiest page (Judgement). | `dashboard/index.html` | S | no | Could |
| L8 | **Page titles that name the record** ("R-2026-00042 · Amira Ben Ali") in `<title>`, so browser tabs and history act as resumption cues. | Cues aid resumption after interruptions [S21][S22]. | reservation, guest, bill templates | S | no | Should |
| L9 | **Sticky action bar** on long pages (reservation, bill) using CSS `position: sticky`. | Keeps the next action visible while scrolling (Judgement). | `app.css` | S | no | Could |

---

## 6. Quick wins

Small (S), high value, no JavaScript, each explainable in one sentence:

1. Room readiness badge on each arrival row (part of R1).
2. Balance or "Paid" on each departure row (R2).
3. Room number in the "Check in" / "Check out" button labels and in the
   success message (R11 a, b).
4. "Guests in the house" card links to an in-house list; fix the "Due
   from guests in the house" link target (R3, L5).
5. Stay total column in New reservation step 3 (R5).
6. Pattern/symbol for Reserved vs Occupied on the availability grid (R7 a).
7. Report presets and a default range (M3 a).
8. Distinct icons for Reports/Availability and Invoices/Backups (L4).
9. Cancel/no-show buttons moved to an "Other actions" block (R11 d, L6).
10. `<title>` that names the reservation or guest (L8).

---

## 7. What the app already does well

Compared with what the sources describe, the app already matches or
exceeds real products on several points worth saying in the demo:

* **Double booking is impossible in the database** (`room_night` primary
  key), not only checked in code; many PMS rely on application checks.
* **Conflicts suggest alternatives** of the same category, as walk-in SOPs
  recommend offering alternatives rather than refusing [S46].
* **Search before register, duplicate warning, unique document:** a
  dailypoint analysis of 4.5 million stays found 2.3 PMS profiles per
  returning guest on average [S15]; the app is designed against exactly
  this.
* **Costs shown before confirming** (cancellation fee, check-out bill) and a
  review step whose confirm works only once: error prevention as NN/g
  describes it, with confirmations only where they matter [S30][S31].
* **Housekeeping cycle with inspection** (To clean → Cleaned, to inspect →
  Ready), the same states OPERA uses (Dirty, Clean, Inspected) [S9];
  check-out and room moves send rooms back to cleaning automatically.
* **Room move keeps history** and offers same-category rooms first, like
  OPERA's room shift/swap [S50].
* **Night audit is idempotent and catches up automatically**, which
  avoids the "audit not run" problem that reviewers and checklists worry
  about [S17][S16].
* **Audit trail that detects tampering** (hash chain), masked identity
  documents with audited reveal: stronger than anything found in the PMS
  documentation studied.
* **Charts use bars, not pies or gauges**, as NN/g recommends [S33].
* **Legend on the availability grid, visible focus, reduced motion, skip
  link, RTL Arabic, light/dark theme**: accessibility basics that review
  complaints ("very small printing") show are not a given [S38].
* **Onboarding tour, checklist and Help page:** answers the training gap
  in the Cloudbeds/NYU survey (85 % trained two weeks or less) [S24][S25].
* **Every action works without JavaScript**: no client-side state to lose,
  fast on old hotel PCs and robust offline, the opposite of the
  "depends on the internet connection" complaint about cloud PMS [S40].

---

## 8. Suggested order before the freeze

**Judgement**, based on cost and the 30 Nov / 14 Dec dates:

1. **Before CP4 (30 Nov), all S, all Must:** R1, R2, R5, R7 a, R11, L5,
   L6, M3 a, and R4 + L2 (search). Together they change the two most-used
   screens (dashboard, reservation) and are easy to show in the demo.
2. **Then, if time allows (Should):** M1 (needs attention), R3, R8, M4,
   M5, L1, L3, L4, L8, R12.
3. **Only if everything above is done (Could):** M2, R6, R9, R10, M6,
   M7, R13, R14, L7, L9.

Each change should follow the usual workflow (issue, branch, tests,
i18n sync for new strings, user guide and Help page update).

---

## Sources

Accessed 31 Oct 2026. Vendor = written by a PMS or software vendor;
Review = user review site; Academic = university or peer-reviewed.

| # | Source | Type |
|---|---|---|
| S1 | Mews Help, "Reservation overview": https://help.mews.com/s/article/reservation-overview | Vendor docs |
| S2 | Cloudbeds Help, "Dashboard – Everything you need to know": https://myfrontdesk.cloudbeds.com/hc/en-us/articles/115000400634 | Vendor docs |
| S3 | protel help, Room type plan (F2): https://help.protel.net/en_US/Listen/Kategoriespiegel.htm ; protel Air check-out: https://connect.protel.net/files/Source/pairexthelp/en_US/ht-check-out.htm ; check-in: https://connect.protel.net/files/Source/pairexthelp/en_US/ht-check-in.htm | Vendor docs |
| S4 | Oracle OPERA Cloud, Managing reservation queue status: https://docs.oracle.com/en/industries/hospitality/opera-cloud/24.2/ocsuh/t_arrivals_in-house_adding_reservation_to_queue.htm ; Batch room assignment: https://docs.oracle.com/en/industries/hospitality/opera-cloud/24.2/ocsuh/t_front_desk_batch_room_assignment.htm | Vendor docs |
| S5 | Oracle OPERA Cloud Digital Assistant (check-in/out conditions): https://docs.oracle.com/en/industries/hospitality/opera-cloud/22.5/ocsuh/c_getting_started_opera_cloud_digital_assistant.htm | Vendor docs |
| S6 | Mews Help, "The Timeline: An overview": https://help.mews.com/s/article/The-Timeline-An-overview | Vendor docs |
| S7 | Hotelogix Jump Start Guide (tape chart): https://www.hotelogix.com/documents/jump_start_guide.pdf | Vendor docs |
| S8 | Cloudbeds, "Getting Started with the New Cloudbeds Calendar": https://myfrontdesk.cloudbeds.com/hc/en-us/articles/48372183498907 ; drag-and-drop troubleshooting: https://myfrontdesk.cloudbeds.com/hc/en-us/articles/219025318 | Vendor docs (first page not readable directly, summary from search) |
| S9 | Oracle OPERA Cloud, "Using the Housekeeping Board": https://docs.oracle.com/en/industries/hospitality/opera-cloud/24.2/ocsuh/t_housekeeping_using_the_housekeeping_board.htm | Vendor docs |
| S10 | Oracle OPERA, Room discrepancies: https://docs.oracle.com/cd/E69137_01/1.20_oh/rmw_room_discrepancies.htm ; setupmyhotel, room status terminology: https://setupmyhotel.com/?p=3481 | Vendor docs / training site |
| S11 | Oracle OPERA Cloud, "About Reservation Alerts": https://docs.oracle.com/en/industries/hospitality/opera-cloud/25.5/ocsuh/c_reservation_alerts.htm | Vendor docs |
| S12 | Oracle OPERA Cloud, "Managing All Reservation and Block Traces": https://docs.oracle.com/en/industries/hospitality/opera-cloud/24.2/ocsuh/t_managing_all_reservation_and_block_traces.htm | Vendor docs |
| S13 | Oracle, OPERA Cloud PMS product tour: https://www.oracle.com/hospitality/hotel-property-management/hotel-pms-software/tour/ | Vendor |
| S14 | Mews feedback, "Knowing how often a guest stayed before": https://feedback.mews.com/forums/955598-guest-experience/suggestions/39881020-knowing-how-often-a-guest-stayed-before-in-the-hot | User forum |
| S15 | Boom PMS, Guest preferences: https://docs.boomnow.com/en/guides/guests/guest-preferences ; dailypoint Profile Snapshot: https://www.hotel-online.com/news/recognize-hotel-vips-in-an-instant-with-profile-snapshot-by-dailypoint ; duplicate-profile figure (dailypoint analysis, found via search; the exact original page was not verified), Hotel-Online "Redefining Hotel Technology": https://www.hotel-online.com/news/redefining-hotel-technology | Vendor |
| S16 | Visual Matrix, "Preparing for Night Audit: Pre-Audit Checklist": https://help.visualmatrix.com/portal/en/kb/articles/preparing-for-night-audit-pre-audit-checklist-cloud | Vendor docs |
| S17 | Prostay, "How to Run a Hotel PMS Demo": https://www.prostay.com/blog/hotel-pms-demo-evaluation-2026/ | Vendor blog |
| S18 | Mews Help, "What is the suggested Operations checklist?": https://help.mews.com/s/article/what-is-the-suggested-operations-checklist | Vendor docs |
| S19 | Mews Help, "The Pickup dashboard in Mews Business Intelligence": https://help.mews.com/s/article/The-Pickup-dashboard-in-Mews-Business-Intelligence | Vendor docs |
| S20 | Alfataftah, "Sorry to Interrupt…: How Work Interruptions Relate to Performance of Hotel Front Office Staff", Auburn University thesis: https://etd.auburn.edu/handle/10415/10452 (PDF: https://auetd.auburn.edu/bitstream/handle/10415/10452/Thesis_Alfataftah_Final.pdf) | Academic (abstract via search; site was unreachable for a full read) |
| S21 | Altmann & Trafton, "Timecourse of recovery from task interruption", Psychonomic Bulletin & Review 2007: https://interruptions.net/literature/Altmann-PBR07.pdf | Academic |
| S22 | Trafton et al., HFES 2005 (salient cues and resumption): https://www.interruptions.net/literature/Trafton-HFES05.pdf ; Monk et al., HFES 2002: https://www.interruptions.net/literature/Monk-HFES02.pdf | Academic |
| S23 | "How and when does multitasking affect customer orientation of hotel employees?", Journal of Hospitality and Tourism Management: https://www.sciencedirect.com/science/article/abs/pii/S1447677021000590 | Academic |
| S24 | Cloudbeds, "The PMS User Experience Report – Key Findings": https://www.cloudbeds.com/hotel-pms-ux/findings/ | Vendor-funded survey with NYU |
| S25 | Hotel Tech Report, "Poor Hotel Tech Is Affecting Employee Retention, Cloudbeds Finds": https://hoteltechreport.com/news/poor-hotel-tech-is-affecting-employee-retention-cloudbeds-finds ; Revfine summary: https://www.revfine.com/pms-common-system-failures/ | Trade press |
| S26 | Melián-González & Bulchand-Gidumal, "Information technology and front office employees' performance", IJCHM 2017: https://accedacris.ulpgc.es/handle/10553/40831 | Academic |
| S27 | Nielsen Norman Group, "Memory Recognition and Recall in User Interfaces": https://www.nngroup.com/articles/recognition-and-recall/ | UX research |
| S28 | Nielsen Norman Group, "Flexibility and Efficiency of Use": https://www.nngroup.com/articles/flexibility-efficiency-heuristic/ ; "UI Accelerators": https://www.nngroup.com/articles/ui-accelerators/ | UX research |
| S29 | Oracle OPERA Cloud, "Using Keyboard Shortcuts": https://docs.oracle.com/en/industries/hospitality/opera-cloud/23.5/ocsuh/cc_using_keyboard_shortcuts.htm | Vendor docs |
| S30 | Nielsen Norman Group, "Preventing User Errors: Avoiding Unconscious Slips": https://www.nngroup.com/articles/slips/ ; "Avoiding Conscious Mistakes": https://www.nngroup.com/articles/user-mistakes/ | UX research |
| S31 | Nielsen Norman Group, "Proximity of Consequential Options": https://www.nngroup.com/articles/proximity-consequential-options/ ; errors topic page: https://www.nngroup.com/topic/errors/ | UX research |
| S32 | W3C, "Understanding SC 1.4.1 Use of Color": https://www.w3.org/WAI/WCAG21/Understanding/use-of-color | Standard |
| S33 | Nielsen Norman Group, "Dashboards: Making Charts and Graphs Easier to Understand": https://www.nngroup.com/articles/dashboards-preattentive/ | UX research |
| S34 | Smartness, "Hotel KPI dashboard: the 12 metrics to track every week": https://www.smartness.com/en/blog/hotel-kpi-dashboard-weekly-metrics ; RevControl, "Pickup as a KPI": https://www.revcontrol.com/blog/173/pickup-as-a-kpi-what-is-it-and-how-can-you-use-it | Vendor blogs |
| S35 | PriceLabs, "How Pacing Reports Drive Smarter Decisions": https://hotels.pricelabs.co/blog/how-pacing-reports-drive-smarter-decisions-and-revenue-growth-in-hotels/ ; RoomMaster pickup template: https://www.roommaster.com/template/hotel-revenue-pickup-template | Vendor blogs |
| S36 | SmartOrder, "Night Audit for OTA Reservations: 8 Exceptions to Review": https://www.smartorder.ai/resources/blog/night-audit-ota-reservations-exceptions/ ; MangoApps night-audit hand-off template: https://www.mangoapps.com/templates/page/sites/hotel-night-audit-handoff?page_slug=page | Vendor blogs |
| S37 | Capterra, Clock PMS reviews: https://www.capterra.com/p/132161/Clock-PMS/reviews/ | Review |
| S38 | Capterra, Hotello reviews (page 3): https://www.capterra.com/p/104276/Hotello-PMS/reviews/?page=3 | Review |
| S39 | Capterra, Hotelogix reviews: https://capterra.com/p/76374/Hotelogix/reviews/?page=5 ; Maestro PMS reviews: https://capterra.com/p/2437/Maestro-PMS/reviews/ | Review |
| S40 | Capterra UK, OPERA Cloud Property Management reviews: https://www.capterra.co.uk/reviews/1034527/opera-cloud-property-management | Review |
| S41 | G2, Cloudbeds comparisons (feature scores): https://www.g2.com/compare/cloudbeds-vs-guesty ; Capterra Cloudbeds: https://www.capterra.com/p/158839/Cloudbeds/ | Review |
| S42 | Capterra, Mews reviews: https://capterra.com/p/145487/Mews-Commander/reviews/ | Review |
| S43 | Mews feedback, "Timeline: Introducing Colour-Coding for Key Booking Insights": https://feedback.mews.com/forums/918232-property-operations-pms/suggestions/50711138-timeline-introducing-colour-coding-for-key-bookin | User forum |
| S44 | Mews feedback, "Improve Timeline visual appearance … accessibility": https://feedback.mews.com/forums/955598-guest-experience/suggestions/49658462-different-colour-options ; "Icon on timeline for space features": https://feedback.mews.com/forums/918232-commander-pms/suggestions/39059956-icon-on-timeline-for-space-features-of-the-guests | User forum |
| S45 | Mews feedback, "Space name in timeline and New Res screens are not consistent": https://feedback.mews.com/forums/918232-property-operations-pms/suggestions/44557611-space-name-in-timeline-and-new-res-screens-are-not ; "Order spaces within the Space category": https://feedback.mews.com/forums/918232-property-operations-pms/suggestions/38247886-order-spaces-within-the-space-category | User forum |
| S46 | Front-office SOP 08 "Walk-in Check-in" (Erasmus+ front office course): https://is.ucp.cz/do/ucp/ffoed/io_2_-_basic_of_front_office_operations/IO2_-_The_Basics_of_Front_Office_Operations/EN/SOPs/Final_SOPs/SOP_08_-_Walk-in_Check-in.pdf ; Sabre SynXis walk-in guest: https://sph-synxisone-help-dr.shs.prod.asc.sabre.com/packages/Help/latest/20014.htm ; RoomMaster, walk-in guest: https://www.roommaster.com/blog/walk-in-guest | Training / vendor docs |
| S47 | Hospitality Tech, "RoomRaccoon introduces housekeeping software": https://hospitalitytech.com/roomraccoon-introduces-housekeeping-software-further-streamline-hotel-operations | Trade press |
| S48 | Oxmaint, "Why Hotels Need Digital Logbooks": https://oxmaint.com/industries/hospitality/digital-logbooks-for-hotels ; "Front Desk Shift Handover Checklist": https://oxmaint.com/industries/hospitality/front-desk-shift-handover | Vendor blogs |
| S49 | SmartOrder, "Hotel Front Desk Shift Handover: What Software Should Record Automatically": https://www.smartorder.ai/resources/blog/hotel-front-desk-shift-handover-software/ | Vendor blog |
| S50 | Oracle OPERA Cloud, "Swapping or Shifting Assigned Rooms": https://docs.oracle.com/en/industries/hospitality/opera-cloud/24.3/ocsuh/t_arrivals_in-house_swapping_or_shifting_assigned_rooms.htm | Vendor docs |

**Limits of this research.** Apaleo, Little Hotelier and eZee publish
little UI documentation; what was found came from marketing and review
listings, so they are not described in detail. Some vendor help pages
(Cloudbeds calendar, Prostay housekeeping board) refused automated
access; for those only search summaries were used. No usability test with
real receptionists was done: the recommendations should ideally be tried
with one or two people (even classmates role-playing a phone call while
a "guest" waits) before the demo.
