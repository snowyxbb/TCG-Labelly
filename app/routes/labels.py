from fastapi import APIRouter, Response

from app.labels import DEFAULT_TEMPLATE

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
