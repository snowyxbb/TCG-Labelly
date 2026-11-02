# AGENTS.md

## What this repo is
- TCG-Labelly: FastAPI backend that generates printable PDF label sheets for trading card collections. Doubles as a hands-on learning workspace for AI-agent tooling (OpenCode-first); MISSION.md and NOTES.md hold that context.
- Learning material is gitignored on purpose: `MISSION.md`, `NOTES.md`, `RESOURCES.md`, `lessons/`, `learning-records/`, `assets/`, `reference/`, `GLOSSARY.md`. Leave it alone — don't commit, clean up, or reorganize it.

## Checks
- Tests: `uv run pytest` (single file: `uv run pytest tests/test_app.py`)
- Lint: `uvx ruff check .`
- CI runs exactly these two, lint first. Run both before claiming work is done or committing.

## Migrations
- Schema changes go through Alembic, never `create_all`. After editing `app/models.py`: `uv run alembic revision --autogenerate -m "<what changed>"`, review the generated file, then `uv run alembic upgrade head`.
- The app runs pending migrations on startup (lifespan → `run_migrations()`).

## Environment
- Python ≥3.14 managed by uv. Always use `uv run` / `uvx` — dependencies live in uv's `.venv`; run `uv sync` after pulling changes.
- User's shell is fish: prefer `;` separators over `and`/`or` chains (they fail in some sandboxes).

## House style
- Ponytail (lazy senior dev) rules are active: smallest change that fully works, no speculative features, end replies with what was skipped and any risk. Full rules live in `.github/copilot-instructions.md` — that is Copilot's steering file, which OpenCode does not read, so don't assume it was loaded anywhere but here.

## Code state
- SQLModel is in use: `app/models.py` (Product table), `app/schemas.py` (request validation), `app/routes/products.py` (CRUD), `app/database.py` (engine + SessionDep).
- ReportLab and Jinja2 are declared but still unused — no PDF/label code exists yet. Don't hunt for it.
