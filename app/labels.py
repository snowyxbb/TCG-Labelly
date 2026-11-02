"""Label-template machinery.

Save-time validation for /label-templates: compile the Jinja2 template,
dry-run render it with sample data, and require the output to parse as
YAML. The PDF render pipeline (Jinja2 -> YAML -> pydantic -> ReportLab
canvas) lands in this module next.
"""

from pathlib import Path
from typing import Any

import yaml
from jinja2 import (
    FileSystemLoader,
    StrictUndefined,
    TemplateSyntaxError,
    UndefinedError,
)
from jinja2.exceptions import SecurityError
from jinja2.sandbox import SandboxedEnvironment

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


def validate_template(template_text: str) -> None:
    """Full save-time validation: the template must compile, render with
    sample data, and produce output that parses as valid YAML."""
    try:
        rendered = _env.from_string(template_text).render(products=[_SAMPLE_PRODUCT])
        yaml.safe_load(rendered)
    except (TemplateSyntaxError, UndefinedError, SecurityError, yaml.YAMLError) as exc:
        raise LabelTemplateError(f"invalid template: {exc}") from exc
