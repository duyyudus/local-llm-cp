# Repository Guidelines

## Project Layout

- This repository is `local-llm-cp`, a control panel for running llama.cpp servers on a
  GPU host: saved launch profiles, start/stop, live server logs, and live GPU usage.
- `llm-cp-server/` is the Python backend under one `uv` environment:
  - `api_server/app/`: FastAPI routers, schemas, services, and database dependencies.
  - `api_server/app/remote/`: everything that touches the GPU host. `executor.py` defines
    the `RemoteExecutor` protocol, with `ssh.py` (asyncssh) and `local.py` (subprocess)
    implementations. `process.py` launches, probes and stops detached processes,
    `logs.py` follows server logs, `gpu.py` samples `nvidia-smi`, `system.py` samples CPU
    and memory from `/proc`, and `engines/` turns a profile into an argv.
  - `api_server/app/runtime.py`: process-wide state (host connection, live run statuses,
    log, GPU and system hubs) created in the FastAPI lifespan.
  - `common/`: configuration, logging, SQLAlchemy models and session helpers.
  - `alembic/`: database migrations. `tests/`: the pytest suite.
- `dashboard/` is the React 19, Vite, TypeScript, Tailwind CSS, daisyUI dashboard, organised
  under `src/app`, `components`, `features`, and `lib`.
- `Dockerfile`, `docker-compose.yml` and `docker-build` cover the `api-server` and
  `dashboard` targets.

## Architecture Notes

- The app never runs llama.cpp itself. It runs shell commands on the GPU host through a
  `RemoteExecutor`; nothing is installed on that host.
- Servers are launched detached (`setsid nohup`) and write to
  `<REMOTE_STATE_DIR>/<profile_id>/server.log`. The `runs` table records the pid so the app
  can reattach after a restart. The host is the source of truth for whether a run is alive;
  `Runtime.refresh` reconciles the table with it.
- A run is only treated as ours when `/proc/<pid>/cmdline` still contains the launched
  executable. Never signal a pid without that check.
- Log and GPU streams are held in process memory and served over SSE, so the API must run
  as a single uvicorn worker.
- Every value interpolated into a remote shell command goes through `shlex.quote`.

## Tooling And Commands

Backend commands apply inside `llm-cp-server/`.

```bash
cd llm-cp-server
uv run pytest
uv run ruff check .
uv run llm-cp migrate
../run-server.sh
```

Set `REMOTE_MODE=local` in `llm-cp-server/.env` to develop without a GPU host; commands then
run on the local machine.

Dashboard commands apply inside `dashboard/`.

```bash
cd dashboard
npm install
npm run dev
npm run build
npm run test
npm run lint
```

Docker, from the repository root:

```bash
./docker-build local --env-file .env.local
```

## Coding Conventions

- Target Python 3.12, line length 100. Ruff is configured with `E`, `F`, `I`, `UP`, `B`,
  and `SIM`; fix lint violations before handing off Python changes.
- Keep routers thin: database and lifecycle logic lives in `api_server/app/services/`,
  host interaction in `api_server/app/remote/`.
- Use the async SQLAlchemy patterns in `common/db/session.py` and
  `api_server/app/db/session.py`.
- Keep comments sparse and only where they clarify non-obvious behaviour.
- For React work, follow the feature/component layout, reuse `dashboard/src/components`,
  keep API types in `dashboard/src/api.ts`, and use lucide icons for icon buttons.
- New inference engines are added as a module in `api_server/app/remote/engines/` exposing
  `build_argv` and `health_url`, registered in `engines/__init__.py`.

## Testing Guidance

- Backend tests run against a temporary SQLite file and `LocalExecutor`, launching
  `tests/stub_server.py` in place of `llama-server`. They need no network, SSH or GPU.
- Dashboard tests use Vitest with a mocked `fetch` and `EventSource`.
- Add or update focused tests for behaviour changes, and run the narrowest useful
  validation before handing off.

## Agent Workflow Notes

- Use Conventional Commit subjects in the form `<type>(<scope>): <imperative summary>`.
- Keep changes scoped to the requested behaviour and avoid unrelated refactors.
- Starting or stopping profiles against a real GPU host affects running models; prefer
  local mode or tests unless the live host is explicitly intended.
