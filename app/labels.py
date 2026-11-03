"""Label-template machinery.

Save-time validation for /label-templates: compile the Jinja2 template,
dry-run render it with sample data, and require the output to be a valid
label-sheet config. The PDF render pipeline (Jinja2 -> YAML -> pydantic
-> ReportLab canvas) lives here too.
"""

from io import BytesIO
from pathlib import Path
from typing import Any, NamedTuple

import yaml
from jinja2 import (
    FileSystemLoader,
    StrictUndefined,
    TemplateSyntaxError,
    UndefinedError,
)
from jinja2.exceptions import SecurityError
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from reportlab.graphics.barcode import code128
from reportlab.graphics.barcode.qr import QrCode
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_TEMPLATE = TEMPLATES_DIR / "default.yaml.j2"


class LabelTemplateError(Exception):
    """A label template failed validation."""


# SandboxedEnvironment: templates are user-supplied, so attribute access to
# Python internals ({{ ''.__class__ }}-style SSTI) must be blocked. Never
# downgrade to plain Environment.
_env = SandboxedEnvironment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    undefined=StrictUndefined,  # typo'd variables must fail loudly at render time
    autoescape=False,  # templates emit YAML, not HTML
    trim_blocks=True,
    lstrip_blocks=True,
)


def _yaml_scalar(value: Any) -> str:
    dumped = yaml.safe_dump(value, allow_unicode=True, default_flow_style=False)
    # PyYAML appends a document-end marker to some scalars (e.g. null);
    # left in place it would split the rendered template into invalid documents
    dumped = dumped.removesuffix("...\n")
    return dumped.strip()


_env.filters["y"] = _yaml_scalar


# Superset of the fields real data provides (Product columns + label
# extras), so templates referencing any real field pass the dry-run.
_SAMPLE_PRODUCT: dict[str, Any] = {
    "id": 1,
    "product_uid": "SAMPLE-UID",
    "full_sku": "SAMPLE-FULL-SKU",
    "sku": "SAMPLE-SKU",
    "variant": "",
    "name": "Sample Product",
    "language": "EN",
    "rarity": "",
    "set_name": "Sample Set",
    "currency": "SGD",
    "price": 10.0,
    "original_price": None,
    "on_sale": False,
    "discount": 0,
    "is_active": True,
    "remarks": "",
    "quantity": 1,
    "qr": None,
    "barcode": None,
}


# ---------------------------------------------------------------------------
# Rendered-template contract: what a template's YAML output must look like.
# ---------------------------------------------------------------------------


class _XY(BaseModel):
    x_mm: float = Field(ge=0)
    y_mm: float = Field(ge=0)


class _QRPlacement(_XY):
    size_mm: float = Field(default=16, gt=0)


class _BarcodePlacement(_XY):
    height_mm: float = Field(default=8, gt=0)


class PageConfig(BaseModel):
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    padding_mm: float = Field(default=3, ge=0)


class LayoutConfig(BaseModel):
    """Optional per-sheet placement; coords are mm from the TOP-LEFT corner.

    A bare text_fields entry stacks on its own line; a nested list joins
    left-to-right on one line using text_separator."""

    text_fields: list[str | list[str]] | None = None
    text_separator: str = " "
    text_origin: _XY | None = None
    font_pt: float | None = Field(default=None, gt=0)
    qr: _QRPlacement | None = None
    barcode: _BarcodePlacement | None = None


class LabelData(BaseModel):
    # extra="allow": templates may emit any field, and text_fields can place it
    model_config = ConfigDict(extra="allow")

    name: str
    price: float
    set_name: str = ""
    sku: str = ""
    currency: str = ""
    original_price: float | None = None
    on_sale: bool = False
    discount: float = 0
    qr: str | None = None
    barcode: str | None = None


class SheetConfig(BaseModel):
    page: PageConfig
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    labels: list[LabelData] = Field(min_length=1)


class _Placements(NamedTuple):
    text_fields: list[str | list[str]]
    text_separator: str
    text_origin: _XY
    font_pt: float
    qr: _QRPlacement
    barcode: _BarcodePlacement


def _resolve_layout(sheet: SheetConfig) -> _Placements:
    """Merge the user's layout over the defaults; everything must fit the page."""
    page, lay = sheet.page, sheet.layout
    pad = page.padding_mm
    resolved = _Placements(
        text_fields=lay.text_fields
        if lay.text_fields is not None
        else ["name", "set_name", "sku", "price"],
        text_separator=lay.text_separator,
        text_origin=lay.text_origin if lay.text_origin is not None else _XY(x_mm=pad, y_mm=pad),
        font_pt=lay.font_pt if lay.font_pt is not None else 8,
        qr=lay.qr
        if lay.qr is not None
        else _QRPlacement(x_mm=page.width_mm - pad - 16, y_mm=page.height_mm - pad - 16),
        barcode=lay.barcode
        if lay.barcode is not None
        else _BarcodePlacement(x_mm=pad, y_mm=page.height_mm - pad - 8),
    )

    def _check(x: float, y: float, w: float, h: float, what: str) -> None:
        if x < 0 or y < 0 or x + w > page.width_mm + 1e-9 or y + h > page.height_mm + 1e-9:
            raise LabelTemplateError(
                f"layout: {what} does not fit on a {page.width_mm:g}x{page.height_mm:g}mm label"
            )

    _check(resolved.text_origin.x_mm, resolved.text_origin.y_mm, 0, 0, "text_origin")
    _check(resolved.qr.x_mm, resolved.qr.y_mm, resolved.qr.size_mm, resolved.qr.size_mm, "qr")
    _check(resolved.barcode.x_mm, resolved.barcode.y_mm, 0, resolved.barcode.height_mm, "barcode")
    return resolved


def _display_price(label: LabelData) -> tuple[str, str | None]:
    """(price text, was-text or None): sale price beats markdown beats plain."""
    currency = f"{label.currency} " if label.currency else ""
    if label.on_sale:
        effective = round(label.price * (1 - label.discount / 100), 2)
        return f"{currency}{effective:.2f}", f"was {currency}{label.price:.2f}"
    if label.original_price is not None and label.original_price > label.price:
        return f"{currency}{label.price:.2f}", f"was {currency}{label.original_price:.2f}"
    return f"{currency}{label.price:.2f}", None


def _text_lines(layout: _Placements, label: LabelData) -> list[str]:
    """Display lines for one label: bare fields stack, nested lists join."""
    lines = []
    for group in layout.text_fields:
        parts = []
        for field in group if isinstance(group, list) else [group]:
            if field == "price":
                price_text, was = _display_price(label)
                parts.append(f"{price_text} ({was})" if was else price_text)
                continue
            value = getattr(label, field, None)
            if value is None or value == "":
                continue
            parts.append(str(value))
        if parts:
            lines.append(layout.text_separator.join(parts))
    return lines


def render_config(template_text: str, products: list[dict[str, Any]]) -> SheetConfig:
    """Render a template with real products and validate the sheet it describes."""
    try:
        rendered = _env.from_string(template_text).render(products=products)
        data = yaml.safe_load(rendered)
    except (TemplateSyntaxError, UndefinedError, SecurityError, yaml.YAMLError) as exc:
        raise LabelTemplateError(f"invalid template: {exc}") from exc
    try:
        config = SheetConfig.model_validate(data)
        _resolve_layout(config)  # bounds check (also catches defaults off tiny pages)
    except ValidationError as exc:
        raise LabelTemplateError(f"invalid label config: {exc}") from exc
    return config


def validate_template(template_text: str) -> None:
    """Full save-time validation: the template must compile, render with
    sample data, and describe a valid label sheet."""
    render_config(template_text, [_SAMPLE_PRODUCT])


def _fit(c: pdf_canvas.Canvas, text: str, font: str, size: float, max_w: float) -> str:
    """Truncate text with an ellipsis so it fits max_w points."""
    if c.stringWidth(text, font, size) <= max_w:
        return text
    while text and c.stringWidth(text + "...", font, size) > max_w:
        text = text[:-1]
    return text + "..."


def _draw_label(c: pdf_canvas.Canvas, page: PageConfig, lay: _Placements, label: LabelData) -> None:
    line_height = lay.font_pt * 1.4  # points
    x = lay.text_origin.x_mm * mm
    max_w = (page.width_mm - lay.text_origin.x_mm - page.padding_mm) * mm
    baseline = (page.height_mm - lay.text_origin.y_mm) * mm - lay.font_pt
    for i, line in enumerate(_text_lines(lay, label)):
        face = "Helvetica-Bold" if i == 0 else "Helvetica"
        c.setFont(face, lay.font_pt)
        c.drawString(x, baseline - i * line_height, _fit(c, line, face, lay.font_pt, max_w))
    if label.qr:
        # quiet-zone border stays at the default (4 modules) for scan reliability
        QrCode(label.qr, width=lay.qr.size_mm * mm, height=lay.qr.size_mm * mm, qrLevel="M").drawOn(
            c, lay.qr.x_mm * mm, (page.height_mm - lay.qr.y_mm - lay.qr.size_mm) * mm
        )
    if label.barcode:
        code128.Code128(label.barcode, barHeight=lay.barcode.height_mm * mm).drawOn(
            c,
            lay.barcode.x_mm * mm,
            (page.height_mm - lay.barcode.y_mm - lay.barcode.height_mm) * mm,
        )


def render_label_sheet(config: SheetConfig) -> bytes:
    """Render the sheet: one PDF page per label, page size = sticker size."""
    lay = _resolve_layout(config)
    page = config.page
    buf = BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=(page.width_mm * mm, page.height_mm * mm))
    for label in config.labels:
        _draw_label(c, page, lay, label)
        c.showPage()
    c.save()
    return buf.getvalue()


def _safe_filename(name: str, ext: str = "yaml") -> str:
    clean = "".join(ch if ch.isascii() and (ch.isalnum() or ch in "-_") else "_" for ch in name)
    return (clean or "template") + "." + ext
