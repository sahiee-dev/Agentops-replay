# AgentOps Replay — Deployment Guide

This document describes how to deploy the AgentOps Replay infrastructure.

---

## Quick Start (Local Development)

```bash
# Start all services
docker-compose up -d

# Verify health
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# View logs
docker-compose logs -f api
```

---

## Services

| Service    | Port | Purpose                           |
| ---------- | ---- | --------------------------------- |
| `postgres` | 5432 | Immutable event store             |
| `api`      | 8000 | Ingestion service (authoritative) |
| `verifier` | —    | On-demand chain validation        |

---

## Environment Variables

### API Service

| Variable       | Required | Default       | Description                   |
| -------------- | -------- | ------------- | ----------------------------- |
| `DATABASE_URL` | Yes      | —             | PostgreSQL connection string  |
| `SECRET_KEY`   | Yes      | —             | JWT signing key               |
| `ENVIRONMENT`  | No       | `development` | `development` or `production` |

### PostgreSQL

| Variable            | Required | Default           |
| ------------------- | -------- | ----------------- |
| `POSTGRES_USER`     | Yes      | `agentops`        |
| `POSTGRES_PASSWORD` | Yes      | —                 |
| `POSTGRES_DB`       | Yes      | `agentops_replay` |

---

## Database Migrations

After starting postgres, run Alembic migrations:

```bash
docker-compose exec api alembic upgrade head
```

---

## Running the Verifier

The verifier runs on-demand using the `tools` profile:

```bash
# Verify a session export
docker-compose run --rm verifier /data/session_export.jsonl

# With strict policy
docker-compose run --rm verifier --require-seal /data/session_export.jsonl
```

---

## Production Deployment

> [!CAUTION]
> The `docker-compose.yml` is for development. Production requires:
>
> - Managed PostgreSQL (RDS, Cloud SQL, etc.)
> - Kubernetes or equivalent orchestration
> - Secrets management (Vault, AWS Secrets Manager)
> - TLS termination (load balancer or sidecar)

### Production Checklist

- [ ] Change `SECRET_KEY` to a secure random value
- [ ] Use managed PostgreSQL with SSL
- [ ] Enable connection pooling (PgBouncer)
- [ ] Configure resource limits
- [ ] Enable audit logging on database
- [ ] Set up backup and restore procedures

---

## Health Checks

| Endpoint  | Method | Expected Response  |
| --------- | ------ | ------------------ |
| `/health` | GET    | `{"status": "ok"}` |

---

## Troubleshooting

### API fails to start

```bash
# Check database connectivity
docker-compose exec api python -c "from app.core.database import engine; engine.connect()"

# Check logs
docker-compose logs api
```

### Database connection refused

```bash
# Ensure postgres is healthy
docker-compose ps postgres

# Check postgres logs
docker-compose logs postgres
```
