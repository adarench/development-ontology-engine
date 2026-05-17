# Local development guide

**In short:** Install dependencies, start Postgres in Docker, apply migrations, run tests. Most work needs no DB; integration tests skip when Postgres isn't reachable.

---

## 1. Prerequisites

```
   ┌─────────────────────────────────────────────────┐
   │  Python 3.9+          (system Python is fine)   │
   │  pip                                            │
   │  Docker + docker-compose  (for the Postgres)    │
   │  git                                            │
   └─────────────────────────────────────────────────┘
```

| Tool | Why | Check |
|---|---|---|
| Python ≥ 3.9 | Runtime | `python3 --version` |
| pip | Install deps | `pip3 --version` |
| Docker | Local Postgres | `docker ps` (daemon must be running) |
| docker-compose | Bring up the substrate | `docker-compose --version` |
| git | Source control | `git --version` |

**Mac note.** If Docker isn't running, start Docker Desktop or `colima start` / `orbstack` — whichever you use to host the daemon.

---

## 2. First-run setup

```bash
git clone <repo> && cd development-ontology-engine

# Install Python deps (system Python is fine; venv is optional)
pip3 install -r requirements.txt

# Copy and edit env vars
cp .env.example .env
# (defaults work for local Postgres in docker-compose; secret values
# like ANTHROPIC_API_KEY go in for AI steps later)

# Start Postgres
docker-compose up -d postgres

# Apply the schema
alembic upgrade head
```

After this you can run the full unit suite:

```bash
python3 -m pytest tests/
```

---

## 3. Daily commands

```
                                ┌─ unit tests (no DB) ──► fast loop
                                │
   pytest tests/  ─────────────►│
                                │
                                └─ integration tests ──► need Postgres
```

| Want to… | Run |
|---|---|
| Run all unit tests (skips DB tests if no Postgres) | `python3 -m pytest tests/ -q` |
| Run a single test file | `python3 -m pytest tests/test_engine_compiler.py` |
| Run integration tests (need Postgres) | `docker-compose up -d postgres && alembic upgrade head && python3 -m pytest tests/test_engine_graph_store.py` |
| Inspect what's in the DB | `docker exec -it tool-engine-postgres psql -U engine -d engine` |
| Re-apply schema after a model change | `alembic revision --autogenerate -m "describe change" && alembic upgrade head` |
| Reset the DB (destroys data) | `docker-compose down -v && docker-compose up -d postgres && alembic upgrade head` |
| Stop everything | `docker-compose down` |

---

## 4. The substrate

**In short:** Postgres in a container, configured via env vars in `.env`. The asyncpg URL is the runtime path; Alembic swaps the driver to `psycopg` for migrations. One DSN, two drivers, single source.

```
   .env                                    docker-compose.yml
   ────                                    ─────────────────
   DATABASE_URL=postgresql+asyncpg:// ┐    ┌── postgres:16-alpine
       engine:engine@localhost:5432/engine │   port: 5432
                                      │    └── volume: tool-engine-pgdata
   POSTGRES_USER=engine                │
   POSTGRES_PASSWORD=engine            │       (data persists across restarts;
   POSTGRES_DB=engine                  │        `down -v` to nuke it)
   POSTGRES_PORT=5432                  │
                                       │
   NOTIFICATION_CHANNELS=inbox         │
                                       │
                                       └─► consumed by:
                                           ─ core/engine/db.py        (async runtime)
                                           ─ migrations/env.py        (Alembic, sync)
```

**`.env` is gitignored.** Real values stay on your machine; the schema is in `.env.example`.

---

## 5. Tests: what runs where

```
   ┌─ Unit (no DB) ─────────────────────────────────────┐
   │  schemas / validator / notifiers / compiler /      │
   │  step library / connectors / renderers / agent     │
   │                                                    │
   │  Fast. Run on every save.                          │
   └────────────────────────────────────────────────────┘

   ┌─ Integration (needs Postgres) ─────────────────────┐
   │  graph store · run lifecycle (M5) · queue (M6)     │
   │                                                    │
   │  Skipped automatically when DATABASE_URL is unset  │
   │  or the DB isn't reachable.                        │
   └────────────────────────────────────────────────────┘
```

**Test fixtures use a savepoint-style transaction** that rolls back at end-of-test, so the DB stays clean between tests. No setup or teardown work needed beyond having Postgres running.

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'sqlalchemy'` | Engine deps not installed | `pip3 install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'yaml'` | PyYAML not installed | `pip3 install PyYAML` (already in requirements.txt) |
| `ValueError: greenlet library is required` | SQLAlchemy async sub-dep missing | `pip3 install greenlet` |
| `failed to connect to the docker API` | Docker daemon not running | Start Docker Desktop / colima / orbstack |
| `psycopg.OperationalError: ... refused` | Postgres container not up | `docker-compose up -d postgres` |
| `password authentication failed for user "engine"` from the host (but `psql` inside the container works) | Host port 5432 is already bound by another process (another colima, another Postgres) — your container can't actually publish 5432 so traffic hits the conflicting service | Change `POSTGRES_PORT` in `.env` (e.g. to `5433`), update `DATABASE_URL` to match, `docker-compose down && docker-compose up -d postgres` |
| `RuntimeError: Event loop is closed` in integration tests | `core.engine.db` caches a module-level engine; pytest-asyncio rotates loops per test | Already handled by an autouse fixture in `tests/test_engine_runner.py`; if you write similar tests, dispose the engine after each via `await dispose_engine()` |
| Alembic complains about missing revision | Local volume drifted from migrations dir | `docker-compose down -v` then `alembic upgrade head` |
| Integration tests skipped | `DATABASE_URL` unset OR Postgres unreachable | Export `DATABASE_URL` and ensure `docker-compose up -d postgres` |
| `pytest_asyncio` warnings about event loop | Older pytest-asyncio + new pytest combo | Already pinned to `pytest-asyncio>=0.23` in `requirements.txt` |

---

## 7. What changes between local and production

| Concern | Local | Production |
|---|---|---|
| Postgres | docker-compose | Managed (Supabase / Neon / RDS / Fly) |
| Secrets | `.env` file | Cloud secret manager → env vars |
| Process model | API + runner in one process | Split when steps get slow |
| AI model | Haiku for cheap iteration | Per-step config; Sonnet/Opus where needed |
| Notifications | `inbox` only | `inbox` + email / Slack (Phase 2+) |
| Auth | Single `system` user (seeded) | Real identity when ≥2 humans share the system |
| Logs | Stdout | Structured JSON shipped to a backend |

**No `if local: ...` branches in code.** Everything that differs comes from env vars; runtime behavior never asks "am I local."

See [`tool_engine_implementation.md` §2](tool_engine_implementation.md#2-environments-local-vs-production) for the full local-vs-prod comparison.

---

## 8. Where things live

```
.
├── core/engine/         orchestration: registry, schemas, compiler, db, store, notifiers
├── core/steps/          step library: data/ transform/ ai/ output/
├── core/lib/            shared framework-free types (empty in Phase 0)
├── migrations/          Alembic migrations + env.py
├── tests/               unit + integration tests
├── docs/                planning & implementation docs
│   ├── tool_engine_plan.md             what + why + phases
│   ├── tool_engine_implementation.md   how each piece is built
│   ├── human_involvement_types.md      the 10 types of human touch
│   └── local_development.md            you are here
└── skills/tool-engine/  SKILL.md guide for building & using tools
```

---

## 9. Going further

- **Building a new step or tool:** [`skills/tool-engine/SKILL.md`](../skills/tool-engine/SKILL.md)
- **Architecture:** [`core/README.md`](../core/README.md)
- **Phase plan:** [`docs/tool_engine_plan.md`](tool_engine_plan.md)
- **Implementation details:** [`docs/tool_engine_implementation.md`](tool_engine_implementation.md)
