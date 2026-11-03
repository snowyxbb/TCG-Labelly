from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlmodel import select

from app.database import SessionDep
from app.labels import (
    DEFAULT_TEMPLATE,
    LabelTemplateError,
    _safe_filename,
    render_config,
    render_label_sheet,
)
from app.models import LabelTemplate, Product
from app.schemas import LabelPdfRequest

router = APIRouter(prefix="/labels", tags=["labels"])


@router.get("/template")
def get_default_template() -> Response:
    """The built-in default template as a YAML file — edit it, then save it
    via POST /label-templates or upload it onto a saved template with
    PUT /label-templates/{id}/file."""
    return Response(
        DEFAULT_TEMPLATE.read_text(encoding="utf-8"),
        media_type="application/x-yaml",
        headers={"Content-Disposition": "attachment; filename=default-label-template.yaml"},
    )


def _template_or_default(template_id: int | None, session: SessionDep) -> tuple[str, str]:
    """(template text, name) for a saved template, or the built-in default."""
    if template_id is None:
        return DEFAULT_TEMPLATE.read_text(encoding="utf-8"), "default-label-template"
    row = session.get(LabelTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return row.template, row.name


def _render_or_422(template_text: str, products: list[dict]) -> bytes:
    try:
        return render_label_sheet(render_config(template_text, products))
    except LabelTemplateError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _pdf_response(pdf: bytes, name: str) -> Response:
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={_safe_filename(name, 'pdf')}"},
    )


@router.get("/pdf")
def render_pdf(
    session: SessionDep,
    ids: Annotated[str, Query(min_length=1)],
    template_id: Annotated[int | None, Query()] = None,
) -> Response:
    """Print labels for database products: one page per unit of quantity."""
    try:
        wanted = [int(part) for part in ids.split(",") if part.strip()]
    except ValueError:
        wanted = []
    if not wanted:
        raise HTTPException(status_code=422, detail="ids must be comma-separated integers")
    rows = {p.id: p for p in session.exec(select(Product).where(Product.id.in_(wanted))).all()}
    missing = [pid for pid in wanted if pid not in rows]
    if missing:
        raise HTTPException(status_code=404, detail=f"products not found: {missing}")
    products = []
    for pid in wanted:
        p = rows[pid]
        data = p.model_dump()
        data["qr"] = p.product_uid
        data["barcode"] = p.full_sku
        products.extend([data] * p.quantity)
    if not products:
        raise HTTPException(status_code=422, detail="no labels to print (all quantities are zero)")
    text, name = _template_or_default(template_id, session)
    return _pdf_response(_render_or_422(text, products), name)


@router.post("/pdf")
def render_pdf_from_data(body: LabelPdfRequest, session: SessionDep) -> Response:
    """Print labels for products sent in the request body (no DB needed)."""
    if body.template is not None and body.template_id is not None:
        raise HTTPException(status_code=422, detail="provide either template or template_id, not both")
    if body.template is not None:
        text, name = body.template, "inline-template"
    else:
        text, name = _template_or_default(body.template_id, session)
    products = [p.model_dump() for p in body.products]
    return _pdf_response(_render_or_422(text, products), name)
