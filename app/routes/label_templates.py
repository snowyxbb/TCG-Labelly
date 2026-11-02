from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import or_, select

from app.database import SessionDep
from app.labels import LabelTemplateError, validate_template
from app.models import LabelTemplate
from app.schemas import LabelTemplateCreate, LabelTemplateUpdate

router = APIRouter(prefix="/label-templates", tags=["label-templates"])


def _validate_or_422(template_text: str) -> None:
    try:
        validate_template(template_text)
    except LabelTemplateError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", status_code=201)
def create_template(data: LabelTemplateCreate, session: SessionDep) -> LabelTemplate:
    _validate_or_422(data.template)
    row = LabelTemplate(**data.model_dump())
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="template name already exists") from None
    session.refresh(row)
    return row


@router.post("/file", status_code=201)
async def create_template_from_file(
    request: Request,
    session: SessionDep,
    name: Annotated[str, Query(min_length=1)],
    description: Annotated[str, Query()] = "",
) -> LabelTemplate:
    """Create a NEW template from a raw YAML file body. The sample from
    GET /labels/template is the intended starting point."""
    try:
        text = (await request.body()).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="template file must be UTF-8 text") from exc
    if not text.strip():
        raise HTTPException(status_code=422, detail="template file is empty")
    _validate_or_422(text)
    row = LabelTemplate(name=name, template=text, description=description)
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="template name already exists") from None
    session.refresh(row)
    return row


@router.get("")
def list_templates(session: SessionDep) -> list[LabelTemplate]:
    return list(session.exec(select(LabelTemplate)).all())


@router.get("/search")
def search_templates(
    session: SessionDep,
    q: Annotated[str, Query(min_length=1)],
) -> list[LabelTemplate]:
    # partial match on name or description, case-insensitive (SQLite LIKE).
    # declared before /{template_id} so "search" isn't swallowed by the path param.
    query = select(LabelTemplate).where(
        or_(
            LabelTemplate.name.contains(q, autoescape=True),
            LabelTemplate.description.contains(q, autoescape=True),
        )
    )
    return list(session.exec(query).all())


@router.get("/{template_id}")
def get_template(template_id: int, session: SessionDep) -> LabelTemplate:
    row = session.get(LabelTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return row


def _safe_filename(name: str) -> str:
    clean = "".join(c if c.isascii() and (c.isalnum() or c in "-_") else "_" for c in name)
    return (clean or "template") + ".yaml"


@router.get("/{template_id}/file")
def download_template_file(template_id: int, session: SessionDep) -> Response:
    """The template as a raw YAML file — edit it and PUT it back."""
    row = session.get(LabelTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return Response(
        row.template,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f"attachment; filename={_safe_filename(row.name)}"},
    )


@router.put("/{template_id}/file")
async def upload_template_file(
    template_id: int, request: Request, session: SessionDep
) -> LabelTemplate:
    """Upload a raw YAML file body as the template text (replaces it)."""
    row = session.get(LabelTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        text = (await request.body()).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="template file must be UTF-8 text") from exc
    if not text.strip():
        raise HTTPException(status_code=422, detail="template file is empty")
    _validate_or_422(text)
    row.template = text
    row.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(row)
    return row


@router.patch("/{template_id}")
def update_template(
    template_id: int, data: LabelTemplateUpdate, session: SessionDep
) -> LabelTemplate:
    row = session.get(LabelTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    updates = data.model_dump(exclude_unset=True)
    if "template" in updates:
        _validate_or_422(updates["template"])
    for key, value in updates.items():
        setattr(row, key, value)
    row.updated_at = datetime.now(UTC)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="template name already exists") from None
    session.refresh(row)
    return row


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: int, session: SessionDep) -> None:
    row = session.get(LabelTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    session.delete(row)
    session.commit()
