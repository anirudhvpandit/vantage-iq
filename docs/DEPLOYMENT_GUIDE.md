# Deployment guide

## Portable single-container deployment

The root `Dockerfile` builds the React frontend and FastAPI backend into one image. It runs on Docker-compatible compute without requiring a separately installed Node or Python runtime. The default Compose profile uses SQLite in a named persistent volume and starts in demo mode.

Requirements on the target machine: Docker Engine/Desktop with the Compose plugin, and network access to package registries on the initial image build.

```sh
cp .env.example .env
docker compose up --build -d
docker compose ps
docker compose logs -f app
```

Open the UI at `http://localhost:8080`. OpenAPI and liveness/readiness are available at `/docs`, `/api/v1/health`, and `/api/v1/ready` on that origin. Data persists in the `vantage_data` volume across container restarts and image upgrades. Do not remove the volume to update the application. Bind access to `127.0.0.1` by default; set `BIND_ADDRESS=0.0.0.0` and add the machine's hostname/IP to `TRUSTED_HOSTS` only when LAN access is intended.

To run the image directly on another Docker host:

```sh
docker build -t vantage-iq .
docker volume create vantage-data
docker run -d --name vantage-iq \
  -p 127.0.0.1:8080:8000 \
  -v vantage-data:/data \
  --env-file .env \
  vantage-iq
```

## Production with external MySQL and SMTP

Copy `.env.example` to a private `.env` and set at minimum:

- `APP_ENV=production`, `DEMO_MODE=false`, `ALLOW_REGISTRATION=false`
- `DATABASE_URL` to the production `mysql+pymysql` endpoint and `DATABASE_SSL_CA_HOST_PATH` to its CA certificate on the container host
- `SECRET_KEY` to a random secret with at least 32 bytes
- `CORS_ORIGINS` and `PUBLIC_APP_URL` to the public HTTPS origin
- `TRUSTED_HOSTS` to the public hostnames plus `localhost` for the container readiness probe
- `SMTP_HOST`, `SMTP_FROM_ADDRESS`, and valid relay credentials if required
- `SESSION_COOKIE_SECURE=true`

Start the service behind a TLS-terminating reverse proxy:

```sh
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d
```

The production overlay mounts the MySQL CA file read-only. PyMySQL verifies the certificate chain and hostname. Configure `FORWARDED_ALLOW_IPS` to the exact proxy IP(s) that connect to the app; do not trust arbitrary forwarded headers. Keep the application port private to the proxy. Use a secret manager rather than committing `.env`.

The default container startup applies Alembic migrations and is appropriate only for a single instance. For a scaled deployment, run one reviewed migration job first (for example `docker compose -f docker-compose.yml -f docker-compose.production.yml run --rm --entrypoint alembic app -c /app/alembic.ini upgrade head`), then set `AUTO_MIGRATE=false` on every application replica.

## Local development without containers

SQLite and direct Python/Vite workflows are also supported. See the root README for setup commands. To serve the built frontend through FastAPI, build the frontend first; otherwise use the Vite development server.

## Validation boundary

The default local Compose profile is self-contained, but this machine does not have Docker/Podman installed, so the image build and container startup could not be exercised here. No production SMTP credentials, MySQL endpoint, or CA were supplied; live mail delivery and MySQL TLS connectivity therefore remain unverified. A production configuration passing local validation is not a production certification. Configure backups, monitoring, restore drills, secret rotation, audit retention, and independent security review before using real business data.
