# TCG-Labelly

Label maker for trading card games. FastAPI backend; generates printable label sheets (PDF) for card collections.

## Develop

```bash
uv sync          # install deps (incl. dev group)
fastapi dev      # dev server on localhost:8000, reload on change
```

## Test & lint

```bash
uv run pytest        # tests
uvx ruff check .     # lint
```
