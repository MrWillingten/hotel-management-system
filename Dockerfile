# Hotel Reservation and Management System – container image (story 6.2).
#
#   docker build -t hotel .
#   docker run -p 127.0.0.1:8000:8000 -v hotel-data:/data hotel
#
# For several workstations use deploy/compose.yaml (HTTPS through Caddy).

# ---------------------------------------------------------------- build stage
# Wheels are built here, so the final image needs no compiler and no pip cache.
FROM python:3.13.16-slim-trixie AS build
WORKDIR /src
COPY requirements.lock pyproject.toml README.md ./
COPY src ./src
# --require-hashes: every dependency must match the hash in the lock file,
# so a tampered package on the index cannot slip into the image.
RUN python -m pip wheel --no-cache-dir --require-hashes -r requirements.lock -w /wheels \
 && python -m pip wheel --no-cache-dir --no-deps . -w /wheels

# ---------------------------------------------------------------- final image
FROM python:3.13.16-slim-trixie
LABEL org.opencontainers.image.title="Hotel Reservation and Management System" \
      org.opencontainers.image.source="https://github.com/MrWillingten/hotel-management-system" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOTEL_DATA_DIR=/data

# The wheels are mounted only for this step, so they do not stay in a layer.
# An unprivileged user with a fixed id: a flaw in the application cannot
# become root inside the container, and the volume's owner is predictable.
RUN --mount=type=bind,from=build,source=/wheels,target=/wheels \
    python -m pip install --no-cache-dir --no-index --find-links=/wheels hotel \
 && groupadd --system --gid 10001 hotel \
 && useradd --system --uid 10001 --gid hotel --home-dir /data --shell /usr/sbin/nologin hotel \
 && mkdir /data && chown hotel:hotel /data && chmod 0700 /data

USER hotel
WORKDIR /data
# Database, secret key, logs and backups: keep them in a volume.
VOLUME ["/data"]
EXPOSE 8000

# No curl in the slim image: the standard library is enough for the check.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --start-interval=2s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status != 200)"]

# Inside a container 0.0.0.0 is required to be reachable at all; only the
# ports published by `docker run -p` or compose are visible from outside.
CMD ["hotel", "run", "--host", "0.0.0.0", "--port", "8000"]
