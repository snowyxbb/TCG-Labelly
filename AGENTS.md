# AGENTS.md

## What this repo is
- TCG-Labelly: FastAPI backend that generates printable PDF label sheets for trading card collections. Doubles as a hands-on learning workspace for AI-agent tooling (OpenCode-first); MISSION.md and NOTES.md hold that context.
- Learning material is gitignored on purpose: `MISSION.md`, `NOTES.md`, `RESOURCES.md`, `lessons/`, `learning-records/`, `assets/`, `reference/`, `GLOSSARY.md`. Leave it alone — don't commit, clean up, or reorganize it.

## Checks
- Tests: `uv run pytest` (single file: `uv run pytest tests/test_app.py`)
- Lint: `uvx ruff check .`
- CI runs ruff, pytest, and a pip-audit dependency scan (lint first). Run ruff + pytest locally before claiming work is done or committing; pip-audit runs in CI only.

## Security posture
- No auth by design: localhost, single-user tool. Before ANY deployment: add auth, switch `fastapi dev` → `fastapi run` behind TLS, revisit CORS and body-size limits.
- User-supplied templates render in a Jinja2 `SandboxedEnvironment` (blocks `__class__`-style SSTI). Never downgrade to plain `Environment`.
- YAML from templates is parsed with `yaml.safe_load`, never `yaml.load`.
- All DB access goes through SQLModel parameterized queries — never build SQL with f-strings.
- Download filenames are sanitized (`_safe_filename`) — keep it that way (header injection).
- `.env` and `*.db` are gitignored; `uv.lock` is committed; CI audits dependencies with pip-audit.

## Migrations
- Schema changes go through Alembic, never `create_all`. After editing `app/models.py`: `uv run alembic revision --autogenerate -m "<what changed>"`, review the generated file, then `uv run alembic upgrade head`.
- The app runs pending migrations on startup (lifespan → `run_migrations()`).

## Environment
- Python ≥3.14 managed by uv. Always use `uv run` / `uvx` — dependencies live in uv's `.venv`; run `uv sync` after pulling changes.
- User's shell is fish: prefer `;` separators over `and`/`or` chains (they fail in some sandboxes).

## House style
- Ponytail (lazy senior dev) rules are active: smallest change that fully works, no speculative features, end replies with what was skipped and any risk. Full rules live in `.github/copilot-instructions.md` — that is Copilot's steering file, which OpenCode does not read, so don't assume it was loaded anywhere but here.

## Code state
- SQLModel is in use: `app/models.py` (Product, LabelTemplate tables), `app/schemas.py` (request validation), `app/routes/` (products CRUD, label-templates CRUD, labels default-template download), `app/database.py` (engine + SessionDep).
- Label templates: YAML+Jinja2 text stored in `labeltemplate`; save-time validation in `app/labels.py` (`render_config`: compile + dry-run render + full pydantic contract validation, so bad `layout:` coords are rejected at save time); default template at `app/templates/default.yaml.j2` (a tutorial for non-technical users), downloadable via GET /labels/template. File round-trip: GET/PUT /label-templates/{id}/file and POST /label-templates/file?name= (raw YAML, no JSON).
- PDF render pipeline is BUILT, all in `app/labels.py`: Jinja2 → YAML → pydantic (`PageConfig`/`LayoutConfig`/`LabelData`/`SheetConfig`) → ReportLab pdfgen canvas. One page per label, page size = the template's `page:` block. QR via ReportLab built-in `reportlab.graphics.barcode.qr.QrCode` (vector, qrLevel="M"), Code128 via `code128.Code128` — zero extra deps beyond ReportLab. Layout: optional `layout:` section in the template (coords mm from top-left; `text_fields` with nested lists joining on one line via `text_separator`); pure helpers `_resolve_layout`/`_text_lines`/`_display_price` are unit-tested. Endpoints: GET /labels/pdf?ids=&template_id= (DB products, qr=product_uid, barcode=full_sku, one label per quantity) and POST /labels/pdf (inline products, template XOR template_id XOR default). `_safe_filename(name, ext)` lives in `app/labels.py` and is shared by both routers. Known limits (documented in the tutorial): no collision detection between placed elements; Helvetica has no CJK glyphs.
