Hotel Reservation and Management System - Windows program
==========================================================

1. Copy hotel.exe anywhere, for example to the Desktop. No installation and
   no Python are needed.

2. Double-click hotel.exe.
   Windows SmartScreen may say "Windows protected your PC", because the
   program is not signed with a paid certificate. Click "More info", then
   "Run anyway". This is asked only once.

3. The first time, the black window asks for the manager account
   (username, full name, password of at least 12 characters).

4. The browser opens the sign-in page at http://127.0.0.1:8000/.
   Keep the black window open while you work; closing it stops the program.

Data (database, backups, logs) is kept in %LOCALAPPDATA%\HotelMedina.
Back up that folder; deleting it deletes all data.

Other commands, from a Command Prompt in the folder of hotel.exe:
  hotel.exe backup                    write a backup now
  hotel.exe reset-password USERNAME   forgotten password
  hotel.exe reset-totp USERNAME       lost two-factor phone
  hotel.exe audit verify              check the audit log
  hotel.exe --help                    every command
