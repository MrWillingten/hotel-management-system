# User guide

This guide explains every page and every button of the application: what
each one does, why it exists, and a short example. It follows a working day
at **Hotel Medina**. The examples use the demo data (`hotel seed --demo`).

* [1. Before you start](#1-before-you-start): roles, signing in, two-factor, language and theme
* [2. A day at the front desk](#2-a-day-at-the-front-desk): the order things usually happen in
* [3. Pages for every staff member](#3-pages-for-every-staff-member)
* [4. Pages and buttons for managers only](#4-pages-and-buttons-for-managers-only)
* [5. Your account](#5-your-account)
* [6. Command-line tools (on the server)](#6-command-line-tools-on-the-server)
* [7. Who can do what (summary)](#7-who-can-do-what-summary)

---

## 1. Before you start

### Two roles

| Role | Who | In one sentence |
|---|---|---|
| **Receptionist** | Front-desk staff | Welcomes guests, books, checks in and out, takes payments. |
| **Manager** | Owner or hotel manager | Everything a receptionist does, plus prices, rooms, staff, discounts, refunds, reports and the hotel's safety tools. |

Nobody creates their own account. The first manager is created on the
server (`hotel create-manager`), and managers create every other account on
the **Staff** page.

### Signing in

1. Open the address you were given (on the hotel computer: `http://127.0.0.1:8000`).
2. Type your **username** and **password**, then **Sign in**.
3. **First time:** you signed in with a *temporary password* chosen by your
   manager. The application immediately asks you to choose your own, and
   you can't open any other page until you do.

*Why:* the manager never knows your real password, and every action
recorded in the audit log really is yours.

**If something goes wrong**

* The message is always the same ("Invalid username or password, or the
  account is temporarily locked"), so an attacker can't learn which
  usernames exist.
* After 5 wrong tries the account is locked for 15 minutes (then 30, 60…).
  A manager can unlock it at once on the Staff page.

### Two-factor sign-in (the code from your phone)

Managers must use it, and receptionists may. After the password, the
application asks for a **six-digit code** from an authenticator app on your
phone (Google Authenticator, Microsoft Authenticator, Aegis, FreeOTP…).

* **Why:** a stolen or guessed password alone is then useless, and a manager
  account can change prices, refund money and read every guest's data.
* **Example:** Mona types her password, then opens Google Authenticator and
  types `482 913` before it changes (a code lasts 30 seconds). She is in.
* **Lost phone?** On the code page, type one of your **recovery codes**
  instead (each works once). If those are gone too, someone with access to
  the server runs `hotel reset-totp mona`.

A new manager sees the reminder "Managers must use two-factor sign-in. Set
it up before …" for 7 days. After that, every page leads to the set-up page
until it is done. See [Two-factor sign-in](#two-factor-sign-in) for how.

### The tour and "Getting started"

A new account sees two cards at the top of the **Dashboard**:

* **Welcome:** **Take the tour** opens a short guided tour, with 6 steps for
  receptionists and 8 for managers (**Back**, **Next**, **Skip the tour**,
  **Finish the tour**). **Not now** hides the invitation. **Help → Restart
  the tour** brings it back at any time.
* **Getting started:** the first tasks to try. Each one ticks itself the
  first time you really do it, because the application reads its own audit
  log. The list disappears when everything is done, or with **Hide this
  list**.

### Language and theme (top bar, on every page)

* **EN / FR / ع:** switches the whole interface to English, French or Arabic.
  Arabic also mirrors the layout from right to left. Your choice is
  remembered on this computer.
* **☀ / 🖥 / ☾:** light theme, follow the computer's setting, or dark theme.

*Example:* a French-speaking receptionist clicks **FR** once; every page,
message and printed invoice is then in French.

### The top bar

* **Your name and role:** opens your account (password, two-factor and,
  for managers, API tokens).
* **Sign out icon (→]):** ends your session at once, and the browser is told
  to forget the pages it cached. Always sign out on a shared computer.

Sessions also end on their own after **30 minutes without activity** or
**12 hours** in total.

---

## 2. A day at the front desk

| When | What | Where |
|---|---|---|
| Morning | Look at today's arrivals, departures and rooms to clean | **Dashboard** |
| Phone call | Is a room free on those dates? | **Availability** or **New reservation** |
| Guest books | Find or register the guest, then book | **New reservation** |
| Guest arrives | Check in; take a deposit if needed | **Dashboard → Check in**, **Bill** |
| During the stay | Add breakfasts, transfers…; change dates; move room | **Reservation** page |
| Guest leaves | Check out: the invoice is issued and printed | **Dashboard → Check out** |
| Housekeeping | Mark rooms cleaned, then inspected | **Dashboard → Housekeeping** or **Rooms** |
| Evening (manager) | Close the day; check the figures | **Night audit**, **Reports** |

---

## 3. Pages for every staff member

### Dashboard

The first page after signing in: what needs attention **today**.

| Element | What it does | Example |
|---|---|---|
| **New reservation** | Starts a booking. | A guest phones for next weekend. |
| **Arrivals** card | Number of guests expected today; click to jump to the list. | "3": three stays start today. |
| **Departures** card | Guests due to leave today. | |
| **Guests in the house** card | Stays currently checked in. | |
| **Occupancy tonight** | Rooms sold ÷ rooms that can be sold tonight (rooms under maintenance are left out). | "75 %", "Under maintenance: 204". |
| **Due from guests in the house** | Money still owed by guests who are staying now. | |
| **Rooms not ready** | Rooms waiting for cleaning or inspection. | |
| **Arrivals list → Check in** | Checks the guest in on the spot. "Late" means the arrival time has passed. | Amira arrives at 15:10: **Check in**. |
| **Departures list → Check out** | Opens the check-out page with the final bill. "Overdue" means the guest should already have left. | |
| **Unpaid after departure** | Invoices still owing money after the guest left. Click to settle them. | A company pays by transfer a week later. |
| **Housekeeping** | Rooms not ready, with a button to move each one to its next state (see [Rooms](#rooms)). | |

### Availability

A calendar grid: **rooms down the side, nights across the top**, two weeks
at a time.

* **Colours:** Free, Reserved, Occupied, Maintenance, Out of service, Past
  (the legend is above the grid).
* **Previous week / Today / Next week:** moves through time.
* **Clicking a free cell** starts a booking for that room from that night.

*Why:* it answers "what is free when?" at a glance, before you even ask
the guest's name.
*Example:* a couple wants 12–14 July. Room 205 is free on both nights, so
you click 205 on the 12th.

### Reservations

**List page.** Every stay, newest arrivals first.

| Element | What it does | Example |
|---|---|---|
| **Code or guest** search | Finds a stay by its code (`R-2026-00042`) or part of the guest's name. | "ben salah" |
| **Status** | Confirmed, Checked in, Checked out, Cancelled, No-show. | Show only *Confirmed* to call guests the day before. |
| **Arriving from / until** | Limits the list to arrivals between two dates. | Next week's arrivals. |
| **Filter** | Applies the search. | |
| Click a code | Opens the reservation page. | |

**New reservation**, in three steps:

1. **Stay:** arrival, departure, number of guests in one room, and an
   optional category. **Find rooms** lists every room free on *every*
   night, with its capacity and price.
2. **Guest:** search by name or document. **Choose** the right person, or
   **Register a new guest** if they're new. A guest marked *do-not-rent*
   is refused.
3. **Rooms:** click **Book** next to one or several rooms. Set adults and
   children for each, add **notes** (arrival time, cot…), then **Review the
   booking**.

The **review page** shows every night with its price, and the total before
tax. **Confirm booking** saves it; **Back** changes something.

* *Why prices are shown per night:* each night's price is **locked** when
  you book. A later price change never alters an existing booking.
* *Why there is a review step:* the confirm button works only once, so a
  double click can't create two bookings.
* *If the room is taken:* the application says which nights clash and
  proposes free rooms of the same category first.

*Example:* Karim, 10–13 July, 2 adults, Deluxe → **Find rooms** → 204 →
**Choose** Karim → **Book** 204 → **Review** (3 × 180 DT = 540 DT) →
**Confirm booking**.

**Reservation page:** everything about one stay.

| Button / part | What it does | When |
|---|---|---|
| **Bill and payments** | Opens the bill (see [Bill](#bill-and-payments)). | Taking a deposit, checking what is owed. |
| **Check in** | Marks the guest as arrived. Possible from the arrival day until the last night. It is refused if the previous guest of that room hasn't left. A warning appears if the room isn't *ready* yet. | The guest is at the desk. |
| **Change** | Changes dates, rooms or the number of people; availability and price are checked again. Nights already booked keep their price; added nights use today's price. Once the guest is in the house, only the departure date and occupants can change. | Extending a stay from 3 to 5 nights. |
| **Move** (next to a room) | Moves the guests to another room **from tonight on** (see below). | The air conditioning broke in 204. |
| **Cancel reservation** | Cancels before arrival. It is free until 48 hours before the arrival time (14:00); after that it costs **20 %** of the accommodation. The page shows the exact fee before you confirm, and **Keep it** leaves the booking unchanged. | The guest calls to cancel. |
| **Record a no-show** | After the arrival time, for a guest who never came. Charged like a late cancellation, and the rooms are freed. | 23:00, nobody arrived. |
| **Check out** | Opens the final bill; **Check out and issue the invoice** finishes the stay. Leaving early charges only the nights spent. | The guest leaves. |
| **Invoice F-2026-00012** | Appears after check-out (or after a fee was charged). | Re-printing an invoice. |
| **Extra services** | Adds a service (breakfast, transfer…) with a quantity and date, only while the guest is checked in. Managers can **Void** a wrong line with a reason (the line stays visible, crossed out). | 2 breakfasts on 11 July. |
| **Nights and prices** | Each night with its room and locked price. | Explaining the bill to the guest. |

**Moving to another room:** the **Move** page lists rooms that are free for
the rest of the stay and big enough, with the same category first.

* By default, every remaining night **keeps its price**: the hotel offers
  the move.
* A **manager** may tick *Charge the new room's price* when the guest asked
  for an upgrade.
* The old room stays on the bill for the nights already spent ("Left on …")
  and is marked *to clean*.

*Example:* Lucas is in 203 since the 10th; on the 11th the shower leaks. You
move him to 202 at the same price, and 203 goes to the cleaning list.

### Bill and payments

The running bill of a stay, shown the same way the invoice will be.

| Part | What it does | Example |
|---|---|---|
| Bill lines | Nights grouped by price, extra services, discounts, taxes (VAT, tourist tax…), total, paid, balance. | |
| **Record a deposit / Record a payment** | Records money received: amount, method (cash, card, bank transfer) and an optional reference. It is never more than the balance due, so a typing mistake can't create a refund to chase. | 100 DT deposit by card, slip no. 5521. |
| **Payments** list | Every payment and refund, with who recorded it. Payments can never be edited or deleted; a mistake is corrected by a refund. | |
| **Refund the guest** *(manager)* | Pays money back when the guest paid too much. | A cancellation fee of 54 DT is taken from a 100 DT deposit: refund 46 DT. |
| **Tax exemptions** *(manager)* | Exempts this stay from one tax, with a reason, until check-out. The exemption is listed on the bill and on the invoice. **Apply the tax again** undoes it. | A Tunisian resident with a foreign passport: exempt from the tourist tax, reason "Resident in Tunisia". |
| **Grant a discount** *(manager)* | A percentage or fixed amount on the accommodation, with a required reason. All discounts together are capped at 30 % of the accommodation. **Remove** cancels one, and stays visible. | 10 % "Returning guest". |

### Guests

**List page.** Search by name, document number, phone or e-mail; accents
and capitals don't matter.

| Button | What it does | Example |
|---|---|---|
| **Register a guest** | Adds a new guest. | |
| **Search** | Finds existing guests. **Always search first**, so returning guests aren't registered twice. | "dupont" |
| **Anonymise old guests** *(manager)* | See [managers](#anonymise-old-guests). | |

**Register / edit a guest:** first and last name, identity document,
nationality, phone, e-mail and notes. Each one is checked:

* **CIN:** 8 digits.
* **Passport:** 6 to 9 letters and digits, with at least one digit.
* **Nationality:** start typing a country in any language ("Tun", "Tunisie",
  "تونس") and pick it from the suggestions.
* **Phone:** a Tunisian number with its 8 digits, or a foreign one with `+`
  and the country code. Numbers that cannot exist are refused.
* **E-mail:** a real address shape, such as `name@example.com`.

* If someone similar already exists, the form shows **"Is it one of these
  guests?"**: open that record instead.
* **This is a different person: register anyway** is only for a real
  namesake.
* A document number can belong to only one guest.

**Guest page**

| Part | What it does | Example |
|---|---|---|
| Identity and contact | The document number is **masked**; **Show** reveals it, and the reveal is recorded in the audit log. | The police ask for a passport number. |
| **Edit guest** | Corrects details (the record is never duplicated). | New phone number. |
| **Flags → VIP guest** | Marks a guest for special attention (shown as a badge everywhere). | A regular guest. |
| **Flags → Do not rent** *(manager)* | Refuses new bookings for this guest; a reason is required. | Unpaid damage last year. |
| **Reservation history** | Every stay of this guest; **New reservation** books for them directly. | |

### Invoices

Every invoice, newest first, searchable by number or guest. An invoice is
issued **at check-out** (and for a cancellation or no-show fee). It gets
the next number in an unbroken sequence (`F-2026-00001`, `00002`…) and
**can never be changed**: corrections are new payments or refunds. Open
one and press **Ctrl+P** to print it or save it as PDF.

*Why:* invoices are legal documents. A gap in the numbers or an edited
invoice would be a red flag in an audit.

### Rooms

**List page.** Every room with its category, capacity, nightly price,
status **tonight** (Available, Reserved, Occupied, Maintenance, Out of
service) and **housekeeping** state. *Category* filters the list.

**Housekeeping:** a room goes **To clean** → **Cleaned, to inspect** → **Ready**.

| Button | What it does | Example |
|---|---|---|
| **Mark cleaned** | The cleaner has finished. | |
| **Mark inspected** | A second person checked it; the room is now **Ready** for a guest. | |
| **Mark to clean** | Sends a room back (a stain was missed). | |

Check-out and room moves put rooms back to *To clean* automatically.

**Room page:** details, the maintenance history, and (managers) the
buttons described in [section 4](#rooms-categories-seasonal-rates-maintenance).

---

## 4. Pages and buttons for managers only

The **Administration** section of the menu appears only for managers.

### Rooms, categories, seasonal rates, maintenance

| Button | What it does | Example |
|---|---|---|
| **Categories** → **Add category** / **Save changes** | Groups rooms (Standard, Deluxe, Suite). You need one before adding rooms. | "Sea view suite". |
| **Add a room** | Number, category, capacity, nightly price (before tax), notes, *In service*. | Room 305, Deluxe, 2 guests, 180 DT. |
| **Edit room** | Changes the same details. Lowering the capacity or taking the room out of service is refused if a future booking would no longer fit; the page names those bookings. | |
| **In service** (untick) | Takes a room out of service for a long time; it can't be booked. | A room turned into an office. |
| **Close for maintenance** | Blocks the room from a first night until it *reopens on* a date, with a reason. It is refused over existing bookings. | Painting 204 from 3 to 6 July. |
| **End now / Cancel** (maintenance history) | Reopens early, or cancels a future closure. | The painters finished a day early. |
| **Seasonal rates → Add rate period** | A different nightly price for one category between two dates. | "Summer 2026", Deluxe, 1 Jul–31 Aug, 220 DT. |
| **Seasonal rates → Remove** | Deletes a period. Bookings already made keep their locked prices. | |

The **weekend rule** shown on that page is set in **Settings**. Pricing
order: rate period, then weekend surcharge, then the room's own price.

### Reports

Figures for any range of up to two years: choose **First night**, **Last
night** and **Availability on**, then **Show**.

| Figure | Meaning |
|---|---|
| **Occupancy** | Nights sold ÷ nights that could be sold (maintenance excluded), per day or month, with a chart. |
| **Average daily rate (ADR)** | Room money ÷ nights sold: the average price actually paid per night. |
| **Revenue per available room (RevPAR)** | Room money ÷ nights that could be sold; it combines price and occupancy. |
| **Invoiced** | Revenue counted when invoices are issued: accommodation, extras, fees, taxes. |
| **Cash received** | Money that really came in, per method (refunds subtracted). |
| **Reservations made, cancellations, no-shows** | Activity in the period, and the fees they produced. |
| **Categories** | Nights and room money per category (which rooms sell). |
| **Availability on …** | Free rooms per category on one day. |
| **Outstanding** | Unpaid invoices plus what guests in the house owe. |

**CSV buttons** download each table for Excel or LibreOffice. Cells that
look like formulas are neutralised so they can't run anything, and every
export is audited.
*Example:* compare July 2026 with July 2025 to decide summer prices.

### Night audit

Closes a finished day: the rooms of guests who never came are released
(no-shows), and a **snapshot** of the day's figures is kept. Guests still
in the house after their departure date are listed, not changed.

* **Close the day** closes yesterday by default. Running it twice changes
  nothing.
* When the application starts after being off, missed days are closed
  automatically ("Automatic" in the list).

*Why:* the day's figures are frozen as they were that night, even if a
payment is recorded later.

### Extra services

The catalogue of things you can charge: breakfast, dinner, airport
transfer, laundry, minibar, spa…

| Button | What it does | Example |
|---|---|---|
| **Add to the catalogue** | Name and unit price before tax. | "Late check-out", 30 DT. |
| **Edit** | New name or price, for **future** charges only; past charges keep their price. | Breakfast goes from 15 to 18 DT. |
| **Active** (untick) | Hides the service from new charges and keeps the history. | A seasonal service. |

### Settings and taxes

| Setting | What it changes | Default |
|---|---|---|
| Check-in / check-out time | When the arrival day starts for fees and no-shows; shown on invoices. | 14:00 / 12:00 |
| Cancellation fee | Share of the accommodation charged for a late cancellation or a no-show. | 20 % |
| Free cancellation until | Hours before arrival. | 48 h |
| Change of mind after booking | Cancelling within this time after booking is always free. | 0 h |
| Maximum total discount | Cap on all discounts of a stay. | 30 % |
| Weekend surcharge and weekend nights | Extra % on chosen nights (the night *starting* on that day). | 0 %, Saturday and Sunday nights |
| Anonymise guests after | Months without a stay before a guest is *proposed* for anonymisation. | 24 |

**The hotel's country** decides who counts as a national for taxes (Tunisia
by default).

**Tax rules → Add tax rule / Edit**:

* a **percentage** on accommodation or extras (VAT), or an **amount per
  adult per night** (tourist tax);
* **Who pays**: everyone, guests not from the hotel's country, or guests
  from it only (decided by the guest's nationality);
* untick *Active* to stop applying a tax.

Issued invoices keep the tax they were issued with. *The demo rates are
examples; check current Tunisian rates.*

### Staff

| Button | What it does | Example |
|---|---|---|
| **Add a staff member** | Username, full name, role and a **temporary password**, which the person must replace at their first sign-in. | Hiring Sami as receptionist. |
| **Save changes** | Name or role. The hotel can never be left without an active manager. | Promoting Sami to manager. |
| **Set temporary password** | For someone who forgot theirs; it also signs them out everywhere. | |
| **Unlock** | Removes a lock caused by wrong passwords. | |
| **Deactivate / Reactivate** | Blocks the account and signs the person out at once. Accounts are never deleted, so the audit log keeps its meaning. | An employee leaves. |

### Audit log

Every important action: who, when, what, from which address, with
details. Filter by user, action and dates. At the top, the application
**verifies the chain**: each entry contains a fingerprint of the previous
one, so editing or deleting an old entry, even directly in the database,
is detected and shown in red.
*Example:* "Who refunded 46 DT on reservation R-2026-00031?"

### Backups

* **Back up now** writes a verified copy of the database.
* The list shows daily, manual, pre-upgrade and pre-restore copies, with
  their size and folder.

A backup is also made automatically each day the program starts, and
before every upgrade or restore. *Copy the backups folder to a USB key or
another computer regularly.* Restoring is done on the server: see
[section 6](#6-command-line-tools-on-the-server).

### Anonymise old guests

Lists guests with no stay for the configured number of months. Tick **I
understand…** and **Anonymise** to erase their personal data (name,
document, contact); this cannot be undone. Invoices keep their copy, as
the law requires.
*Why:* personal data shouldn't be kept longer than needed (data protection).

### Manager-only buttons on other pages

* **Grant a discount**, **Refund the guest**: on the bill.
* **Void** an extra service: on the reservation.
* **Do not rent**: on the guest page.
* **Charge the new room's price**: when moving a guest.
* **API tokens**: in your account (below).

---

## 5. Your account

Click your name in the top bar.

### Password

**Current password**, **New password** (at least 12 characters; a short
sentence is easy to remember and hard to guess; very common passwords are
refused), **Repeat**, then **Change password**. Your *other* sessions are
signed out.

### Two-factor sign-in

1. Install an authenticator app on your phone.
2. In the app, add an account and **scan the QR code** (or type the key
   shown under it).
3. Type the code the app shows, then **Turn on two-factor sign-in**.
4. **Write down the 10 recovery codes** shown next. They are shown only once,
   and each one works once if the phone is lost.

Afterwards the page shows how many recovery codes are left:

* **Create new recovery codes** (needs a current code) replaces them all.
* **Turn off** is available to receptionists only; managers must keep it.

### API tokens (managers)

Let another program (a spreadsheet, a dashboard) **read** rooms,
availability, reservations and report figures through the JSON API. A
token can never change anything.

* **Create the token:** name and lifetime (30, 90 or 365 days). **Copy it
  at once**; it is never shown again.
* **Revoke:** stops it immediately.

*Example:* "Occupancy screen in the office", 90 days. Details for the
person setting up the program: [api.md](api.md).

---

## 6. Command-line tools (on the server)

Run them in a terminal in the program's folder:
`python -m hotel …` (or `hotel.exe …` on the Windows program).

| Command | Use |
|---|---|
| `run` | Start the application (`--open-browser` opens the page). |
| `create-manager` | Create the very first manager. |
| `reset-password USERNAME` | Forgotten password, even the last manager's. |
| `reset-totp USERNAME` | Lost phone and recovery codes. |
| `backup` / `restore FILE` | Back up now; restore a backup (stop the application first). |
| `night-audit [--date]` | Close a day from the command line. |
| `audit verify` | Check the audit log's chain. |
| `seed --demo` | Fill an empty hotel with fictional demo data. |
| `version` | Show the version. |

---

## 7. Who can do what (summary)

| | Receptionist | Manager |
|---|---|---|
| Dashboard, availability, reservations (book, change, move at the same price, cancel, check in/out, no-show) | ✅ | ✅ |
| Guests (register, edit, VIP flag, reveal document), invoices, bills, payments | ✅ | ✅ |
| Housekeeping states | ✅ | ✅ |
| Discounts, refunds, voiding a charge, do-not-rent, move at the new price | | ✅ |
| Rooms, categories, prices, maintenance, extras catalogue, settings, taxes | | ✅ |
| Staff, reports, night audit, audit log, backups, anonymisation, API tokens | | ✅ |
| Two-factor sign-in | optional | required |

The full table, generated from the application's routes, is in
[security.md → Authorization matrix](security.md#authorization-matrix).
