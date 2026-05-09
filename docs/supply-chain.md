# Supply Chain Notes

Last reviewed: 2026-05-09

## Python services

The API services use direct dependencies from the official PyPI package index and
pin exact versions in each service `requirements.txt`.

| Package | Version | Used by | Source / project |
| --- | ---: | --- | --- |
| FastAPI | 0.136.1 | `todo-api`, `user-api` | `pypi.org/project/fastapi/` |
| HTTPX | 0.28.1 | `todo-api` | `pypi.org/project/httpx/` |
| Psycopg | 3.3.4 | `todo-api`, `user-api` | `pypi.org/project/psycopg/` |
| Pydantic | 2.13.4 | `todo-api`, `user-api` | `pypi.org/project/pydantic/` |
| PyJWT | 2.12.1 | `user-api` | `pypi.org/project/PyJWT/` |
| SQLAlchemy | 2.0.49 | `todo-api`, `user-api` | `pypi.org/project/SQLAlchemy/` |
| Uvicorn | 0.46.0 | `todo-api`, `user-api` | `pypi.org/project/uvicorn/` |
| Pytest | 9.0.3 | tests | `pypi.org/project/pytest/` |

## Audit result

`pip-audit` was run against both API services:

```text
python -m pip_audit -r apps/todo-api/requirements.txt -r apps/todo-api/requirements-dev.txt
No known vulnerabilities found

python -m pip_audit -r apps/user-api/requirements.txt -r apps/user-api/requirements-dev.txt
No known vulnerabilities found
```

## Notes

- Production should inject `SECRET_KEY` and `SERVICE_AUTH_TOKEN` through a secret
  manager or deployment environment, not commit production values to git.
- The services fail fast in `APP_ENV=production` if local development secrets are
  still in use.
- Re-run `pip-audit` before releases and whenever dependency pins change.
- Consider adding hash-locked requirements or a lockfile once the project chooses
  a Python package manager workflow.
