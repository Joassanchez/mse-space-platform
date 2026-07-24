# Verification Report — Phase 1 Foundation (PR #1)

**Change**: argplant-data-service
**Phase**: 1 of 5 (Foundation only)
**Branch verified**: `feature/argplant-data-service-01-foundation`
**PR target**: `feature/argplant-data-service` (tracker)
**Date**: 2026-07-24
**Verifier**: sdd-verify (sdd-verify skill)
**Mode**: Standard (no TDD enforcement — greenfield project)

---

## Verdict

**status: partial** — Foundation is structurally complete and matches the design at the package/layout level. All 16 Phase 1 tasks have produced real artifacts. There is **1 CRITICAL issue** that will block the database from initializing on a fresh stack, and several lower-severity items worth addressing before merge.

---

## CRITICAL Findings

### C-1: `gen_random_uuid()` used without enabling the `pgcrypto` extension

**Where**: `migrations/versions/001_initial.py` (lines 22, 33, 55, 76, 92)

**Problem**: The migration calls `gen_random_uuid()` as the default for all five `id` columns, but no `CREATE EXTENSION` statement exists. In PostgreSQL 13+, `gen_random_uuid()` lives in the `pgcrypto` extension. The `postgis/postgis:16-3.4` image does **not** enable pgcrypto by default — it ships postgis + its dependencies only.

**Impact**: `alembic upgrade head` against a fresh database will fail with `function gen_random_uuid() does not exist`. This is the very first step a developer or CI runner will hit when bootstrapping the stack.

**Fix** (add at the top of `upgrade()`, before the first `create_table`):

```python
op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
```

**Why it passed earlier**: Nothing in Phase 1 actually runs the migration against a real DB — `tests/conftest.py` uses SQLite (`sqlite+aiosqlite://`) which has its own random UUID generation, so this bug is invisible to the local test suite but fatal in Docker.

---

## WARNING Findings

### W-1: Compose validation required a `.env` file that the repo does not ship

**Where**: `docker-compose.yml` (line 32) — `env_file: .env`

**Problem**: The api and worker services both reference `env_file: .env`. Running `docker compose config` against a fresh checkout fails:

```
env file ...\.env not found
```

**Impact**: A new contributor running `make up` (or even just `docker compose config` to validate) will see this error. The verification step "docker compose config validates" cannot be reproduced without first creating a `.env`.

**Fix options**:
- (a) Document `.env` creation in README (`cp .env.example .env` first).
- (b) Remove `env_file: .env` from compose and pass values via inline `environment:` block with defaults.
- (c) Use `env_file: .env` only when the file exists (Docker Compose does not support optional `env_file` directly; the workaround is a `.env` stub in the repo or compose `env_file: [".env", ".env.example"]`).

**Recommendation**: (a) — `.env.example` exists precisely for this, and copying it is the standard pattern. Just add a one-line note to the README so it's not a gotcha.

### W-2: Worker service references a module that does not yet exist

**Where**: `docker-compose.yml` line 44 — `command: arq argplant.modules.ingestion.worker.WorkerSettings`

**Problem**: `argplant/modules/ingestion/worker.py` is a Phase 5 deliverable (task 5.2). The foundation compose file already tries to start the worker, which will fail with `ModuleNotFoundError` until Phase 5 lands.

**Impact**: `make up` starts db + redis + api successfully, but the `worker` container will keep restarting.

**Fix options**:
- (a) Comment out the `worker:` service in Phase 1; re-enable in Phase 5.
- (b) Leave as-is and add a `condition: service_started` or note in README that the worker is disabled until Phase 5.
- (c) Add a minimal `worker.py` stub now that imports a no-op `WorkerSettings`.

**Recommendation**: (a) — the cleanest, since the worker has no purpose until the ingestion module exists.

### W-3: `test_default_database_url` is a tautology

**Where**: `tests/unit/test_shared.py` line 12

```python
def test_default_database_url(self, mock_settings):
    assert "postgresql+asyncpg" in mock_settings.DATABASE_URL or "sqlite" in mock_settings.DATABASE_URL
```

**Problem**: The fixture (`mock_settings`) explicitly overrides `DATABASE_URL` to `sqlite+aiosqlite://`, so the assertion always passes regardless of the default in `Settings`. The test proves nothing about the configured default.

**Fix**: Either test the actual default by reading `Settings()` without overrides, or remove the test.

### W-4: `event_loop` session-scoped fixture uses the deprecated pattern

**Where**: `tests/conftest.py` lines 24–29

The `event_loop` fixture override is the old pytest-asyncio (< 0.21) workaround. Modern pytest-asyncio auto-handles this. With `asyncio_mode = "auto"` in `pyproject.toml`, this fixture can be removed entirely.

**Impact**: None functionally today, but pytest-asyncio 0.23+ (the declared dep) emits a `DeprecationWarning` for this exact pattern. Lint pass will surface it.

---

## SUGGESTION Findings

### S-1: `slowapi` is declared in pyproject.toml but not used

`argplant/shared/middleware.py` implements a custom `RateLimiterMiddleware` using `redis.asyncio` directly. `slowapi` is in `dependencies` but has no consumer. The design's architecture table says "slowapi **or** Redis sliding-window middleware" — you chose the Redis route, which is fine. Drop `slowapi` from `pyproject.toml` to avoid carrying an unused dep.

### S-2: `worker` port `[]` is unusual style

`docker-compose.yml` line 43 uses `ports: []` to clear the YAML anchor. It works, but `ports: !reset []` or splitting the worker into its own block (not using the anchor) is more idiomatic.

### S-3: Add a README with the `cp .env.example .env` step

Even if you only ship a 10-line README, the "first-time setup" sequence is invisible otherwise.

### S-4: `Makefile` `seed` target references modules that don't exist yet

`make seed` will fail until Phase 4 lands. Acceptable for foundation — but a `make seed` target that does nothing useful today is a footgun. Consider gating it: `seed: migrate` with a `phase-4` label, or remove until then.

### S-5: `CORS_ORIGINS=["*"]` in `.env.example` works only because pydantic-settings parses JSON for list fields

Pydantic-settings v2 parses list env vars as JSON by default. `["*"]` will parse to `["*"]`. **But** if a user writes `*` (unquoted) in their `.env`, it will fail. Worth a one-line comment in `.env.example` explaining the JSON list format.

---

## Spec Compliance (Foundation-Relevant)

| Spec criterion (from task 1.x) | Status | Evidence |
|---|---|---|
| 1.1 pyproject.toml with declared deps | PASS | `pyproject.toml:10-23` lists all 13 deps; missing `slowapi` only as a *used* lib (see S-1) |
| 1.2 Multi-stage Dockerfile | PASS | `Dockerfile` has `builder` and `runtime` stages, slim base, correct CMD |
| 1.3 docker-compose with db/redis/api/worker + healthchecks | PARTIAL | Compose config valid; healthchecks on db+redis present (api+worker have none, which is OK); see W-1, W-2 |
| 1.4 Makefile with up/down/test/lint/seed/migrate/migration | PASS | `Makefile:1-22` defines all 7 targets |
| 1.5 `.env.example` with all design keys | PASS | `env.example` has all 14 env vars; matches `config.py` exactly |
| 1.6 Empty `__init__.py` for argplant and shared | PASS | Both exist (0 bytes), importable |
| 1.7 Settings model with all design fields | PASS | `config.py` has every field from design; `SettingsConfigDict(env_file=".env", extra="ignore")` correct |
| 1.8 Async SQLAlchemy engine + session + get_session | PASS | `database.py` exposes engine, async_session, Base, get_session; uses `expire_on_commit=False` |
| 1.9 Redis cache with get_json/set_json/get_stale/delete | PASS | All four helpers present; `set_json` writes both fresh and stale via pipeline |
| 1.10 StorageBackend Protocol + LocalStorage | PASS | Protocol defines save/exists/get_path; LocalStorage uses `mkdir(parents=True)` |
| 1.11 IP rate limiter with Redis INCR+EXPIRE, 429+Retry-After | PASS | `middleware.py:14-59` does exactly this; also has `add_stale_header` helper |
| 1.12 FastAPI app with CORS, lifespan, /health | PASS | `main.py:41-68` wires CORSMiddleware + RateLimiterMiddleware + lifespan + `/health` |
| 1.13 Alembic async config + initial migration with 5 tables + indexes | PARTIAL | `env.py` is async-compatible; migration creates all 5 tables + 3 indexes (matches design). **Fails on fresh DB** — see C-1 |
| 1.14 Test harness fixtures | PASS | `conftest.py` has test_engine, test_session, test_redis (fakeredis), test_client (httpx ASGI), mock_settings; pytest-asyncio auto mode set in pyproject |
| 1.15 Unit tests for shared infrastructure | PARTIAL | Tests exist (12 total) but `test_default_database_url` is tautological (W-3). Others are meaningful |
| 1.16 Integration test for /health | PASS | `test_health.py` checks 200 + body shape |

**Spec coverage for the foundation-touching spec requirements**:

- `agroclimate-data` "IP-Based Rate Limiting" → middleware + header + tests → **deferred to Phase 2 for end-to-end verification, but rate limiter mechanism is foundation-validated**
- `satellite-data` "Async Sentinel Download" → storage abstraction is in foundation → **deferred to Phase 3**
- `data-ingestion-pipeline` "Async Satellite Download Jobs" → foundation provides table + storage; **deferred to Phase 5**

No spec criteria from Phases 2-5 are expected to be verified at foundation stage.

---

## Environment Limitations

The verification was run on a machine **without Python and without a running Docker daemon**. Therefore:

- `pytest tests/ -v` was **not executed**. Static review only.
- `pip install -e .` was **not executed**. Manifest is correct per static review.
- `ruff check argplant/` was **not executed**. Code style appears consistent (PEP 8, type hints present, docstrings on all public symbols).
- `docker compose build` was **not executed**.
- `alembic upgrade head` was **not executed** — but the missing-extension bug (C-1) was caught by code review, so this counts as a finding.

The orchestrator should run the full test + lint pass in a Linux CI environment before final merge.

---

## What Passed Cleanly

- All 16 tasks have real, non-stub files in the working tree.
- `git log` shows 7 well-scoped commits, conventional-commit style, no AI attribution.
- Package structure exactly matches the design's tree.
- DB schema in the migration matches the design's DDL (5 tables, 3 indexes, FK constraint, unique constraints).
- No hardcoded production credentials anywhere — only the dev-default `argplant:argplant@localhost` in three places, which matches the dev DB in compose.
- `.gitignore` properly excludes `.env`, `data/satellite/*`, `pgdata/`, virtual envs.
- Pydantic-Settings has `extra="ignore"` so unknown env vars won't break startup.
- CORS middleware is registered before rate limiter, and the rate limiter has graceful-degradation if Redis is down.

---

## Recommendations (priority order)

1. **Fix C-1** (`CREATE EXTENSION pgcrypto`) before merge. One-line change, no risk.
2. **Fix W-1 + W-2** (compose forward-references) before merge. Either add README setup steps and comment out the worker service, or stub the worker module.
3. **Fix W-3** (tautological test) — trivial rewrite, then the test actually validates something.
4. Address W-4 and S-1..S-5 in a follow-up commit or PR-cleanup.

After C-1 and W-1/W-2 are addressed, Phase 1 is **ready for archive** and the tracker PR can absorb it.

---

## Artifacts

- This report: `openspec/changes/argplant-data-service/verify-report-01-foundation.md`
- Engram: `sdd/argplant-data-service/verify-report` (capture_prompt: false)
