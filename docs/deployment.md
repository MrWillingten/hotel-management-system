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

## Data folder

Everything the application writes lives in `HOTEL_DATA_DIR` (default
`./instance`): the database `hotel.db`, the `secret_key` file and `logs/`.

* Keep it on a **local disk**: SQLite's write-ahead log is not safe on network shares.
* Restrict access to it (it contains guest personal data) and use full-disk
  encryption (BitLocker on Windows, LUKS on Linux).
* Never commit it: it is listed in `.gitignore`.
* Deleting `secret_key` signs everyone out; deleting `hotel.db` deletes all data.

## Configuration reference

| Variable | Default | Meaning |
|---|---|---|
| `HOTEL_ENV` | `production` | `production`, `development` (debugger, auto-reload) or `testing` |
| `HOTEL_DATA_DIR` | `./instance` | Data folder |
| `HOTEL_NAME` | `Hotel Medina` | Name shown in the interface |
| `HOTEL_TIMEZONE` | `Africa/Tunis` | Time zone used for "today" and the 48-hour rule |
| `HOTEL_HTTPS` | off | See above |
| `HOTEL_TRUSTED_PROXIES` | `0` | See above |
