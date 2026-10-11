# Running the application

## On one computer (default)

`python -m hotel run` starts the production server (Waitress) on
`http://127.0.0.1:8000`. Only that computer can reach it. This is the
recommended setup for a single reception desk.

## Several computers on the hotel network

Listening on a network address (`--host 0.0.0.0`) without HTTPS would send
passwords in clear text over the network, so the application prints a warning.
Put an HTTPS reverse proxy in front instead. [Caddy](https://caddyserver.com/)
is a single program for Windows and Linux that can create its own local
certificate authority:

```
# Caddyfile
hotel.lan {
    tls internal
    reverse_proxy 127.0.0.1:8000
}
```

Then start the application with:

| Variable | Value | Effect |
|---|---|---|
| `HOTEL_HTTPS` | `1` | Cookies get the `Secure` flag; HSTS header is sent |
| `HOTEL_TRUSTED_PROXIES` | `1` | Client addresses are read from the proxy's `X-Forwarded-For` (needed for login throttling) |

Each workstation must trust Caddy's local root certificate once.

## With Docker

The image runs the same production server (Waitress) as an unprivileged user
(uid 10001), keeps all data in the `/data` volume and reports its state on
`/health`, which Docker checks every 30 seconds.

**One computer**, reachable only from itself:

```
docker build -t hotel .
docker run -d --name hotel -p 127.0.0.1:8000:8000 -v hotel-data:/data hotel
docker exec -it hotel hotel create-manager
```

**Several workstations, with HTTPS** – `deploy/compose.yaml` starts the
application behind Caddy:

```
cd deploy
HOTEL_DOMAIN=hotel.lan docker compose up -d
docker compose exec -it hotel hotel create-manager
```

* The application's port is not published; only Caddy (ports 80 and 443) is.
  `HOTEL_HTTPS=1` and `HOTEL_TRUSTED_PROXIES=1` are already set.
* The container's file system is read-only except `/data` and `/tmp`; it
  runs with no Linux capabilities and cannot gain privileges.
* Each workstation must trust Caddy's root certificate once. Copy it out with
  `docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt .` and
  import it (Windows: double-click → Install → *Trusted Root Certification
  Authorities*). `HOTEL_DOMAIN` must resolve to the server (router DNS or
  each PC's `hosts` file).
* Every `hotel` command works inside the container, for example
  `docker compose exec hotel hotel backup` or `... hotel reset-totp mona`.
  Backups are written to `/data/backups`, inside the volume: copy them off
  the server too (`docker compose cp hotel:/data/backups ./backups`).
* To restore: `docker compose stop hotel`, then
  `docker compose run --rm hotel hotel restore /data/backups/FILE`, then start again.
* A bind mount instead of the named volume must be owned by uid 10001.

## Data folder

Everything the application writes lives in `HOTEL_DATA_DIR` (default
`./instance`): the database `hotel.db`, the `secret_key` file and `logs/`.

* Keep it on a **local disk**: SQLite's write-ahead log is not safe on network shares.
* Restrict access to it (it contains guest personal data) and use full-disk
  encryption (BitLocker on Windows, LUKS on Linux).
* Never commit it: it is listed in `.gitignore`.
* Deleting `secret_key` signs everyone out; deleting `hotel.db` deletes all data.

## Backups

* A backup is written automatically when the application starts, at most
  once every 24 hours; the 14 most recent daily backups are kept.
* A backup is also written before every database upgrade, and before a restore.
* Managers can take one at any time from **Backups**, or run `python -m hotel backup`.
* For a server that runs for weeks without restarting, schedule
  `python -m hotel backup` daily (cron on Linux, Task Scheduler on Windows).
* To restore: stop the application, then run `python -m hotel restore FILE`.

## Configuration reference

| Variable | Default | Meaning |
|---|---|---|
| `HOTEL_ENV` | `production` | `production`, `development` (debugger, auto-reload) or `testing` |
| `HOTEL_DATA_DIR` | `./instance` | Data folder |
| `HOTEL_NAME` | `Hotel Medina` | Name shown in the interface |
| `HOTEL_TIMEZONE` | `Africa/Tunis` | Time zone used for "today" and the 48-hour rule |
| `HOTEL_HTTPS` | off | See above |
| `HOTEL_TRUSTED_PROXIES` | `0` | See above |
