# Runbook

## Local Smoke Test

```bash
docker compose up --build
curl http://localhost:4001/health
curl http://localhost:4002/health
```

## Expected Health Responses

Both APIs should return JSON with `ok: true` and the service name.

## Common Checks

- Confirm Postgres is reachable at `localhost:5432`.
- Confirm Redis is reachable at `localhost:6379`.
- Review service logs with `docker compose logs -f <service-name>`.

