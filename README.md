# TCG-Labelly

Label maker for trading card games. FastAPI backend; generates printable label sheets (PDF) for card collections.

## Status

Products API is live: CRUD, search (`/products/search?q=`), sale/discount toggling — backed by SQLite via SQLModel. PDF label generation is not built yet.

## Develop

```bash
uv sync          # install deps (incl. dev group)
fastapi dev      # dev server on localhost:8000, reload on change
```

Schema changes go through Alembic (runs automatically on server start):

```bash
uv run alembic revision --autogenerate -m "what changed"   # after editing app/models.py
uv run alembic upgrade head                                # apply
```

## Test & lint

```bash
uv run pytest        # tests
uvx ruff check .     # lint
```
