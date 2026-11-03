"""PDF renderer + /labels/pdf endpoint tests."""

import pytest

from app.labels import (
    _SAMPLE_PRODUCT,
    LabelData,
    LabelTemplateError,
    LayoutConfig,
    PageConfig,
    SheetConfig,
    _display_price,
    _resolve_layout,
    _text_lines,
    render_config,
    render_label_sheet,
)


def _label(**over):
    data = {
        "name": "Bolt",
        "price": 10.0,
        "currency": "SGD",
        "sku": "2XM-123",
        "variant": "",
        "set_name": "Double Masters",
    }
    data.update(over)
    return LabelData(**data)


def _sheet(**over):
    return SheetConfig(
        page=over.pop("page", PageConfig(width_mm=60, height_mm=40, padding_mm=3)),
        layout=over.pop("layout", LayoutConfig()),
        labels=over.pop("labels", [_label()]),
    )


# ---- pure helpers ---------------------------------------------------------


def test_display_price_plain():
    assert _display_price(_label()) == ("SGD 10.00", None)


def test_display_price_on_sale():
    assert _display_price(_label(on_sale=True, discount=20)) == ("SGD 8.00", "was SGD 10.00")


def test_display_price_markdown():
    assert _display_price(_label(original_price=15.0)) == ("SGD 10.00", "was SGD 15.00")


def test_text_lines_stack_and_join():
    lay = _resolve_layout(
        _sheet(layout=LayoutConfig(text_fields=["name", ["sku", "variant"], "price"]))
    )
    assert _text_lines(lay, _label(variant="Collector")) == ["Bolt", "2XM-123 Collector", "SGD 10.00"]


def test_text_lines_group_of_three():
    lay = _resolve_layout(
        _sheet(layout=LayoutConfig(text_fields=[["sku", "variant", "set_name"]], text_separator=" | "))
    )
    assert _text_lines(lay, _label(variant="Collector")) == ["2XM-123 | Collector | Double Masters"]


def test_text_lines_skips_empty_values():
    lay = _resolve_layout(_sheet(layout=LayoutConfig(text_fields=[["sku", "variant"]])))
    assert _text_lines(lay, _label()) == ["2XM-123"]


def test_resolve_layout_defaults():
    lay = _resolve_layout(_sheet())
    assert lay.text_fields == ["name", "set_name", "sku", "price"]
    assert (lay.text_origin.x_mm, lay.text_origin.y_mm) == (3, 3)
    assert (lay.qr.x_mm, lay.qr.y_mm, lay.qr.size_mm) == (41, 21, 16)
    assert (lay.barcode.x_mm, lay.barcode.y_mm, lay.barcode.height_mm) == (3, 29, 8)


def test_resolve_layout_override_wins():
    lay = _resolve_layout(_sheet(layout=LayoutConfig(qr={"x_mm": 1, "y_mm": 2, "size_mm": 5})))
    assert (lay.qr.x_mm, lay.qr.y_mm, lay.qr.size_mm) == (1, 2, 5)


def test_resolve_layout_rejects_out_of_bounds():
    with pytest.raises(LabelTemplateError):
        _resolve_layout(_sheet(layout=LayoutConfig(qr={"x_mm": 50, "y_mm": 0, "size_mm": 16})))


# ---- render pipeline ------------------------------------------------------


def test_render_config_with_default_template():
    from app.labels import DEFAULT_TEMPLATE

    config = render_config(DEFAULT_TEMPLATE.read_text(encoding="utf-8"), [_SAMPLE_PRODUCT])
    assert config.page.width_mm == 60
    assert len(config.labels) == 1


def test_render_config_rejects_missing_page():
    with pytest.raises(LabelTemplateError):
        render_config("labels:\n  - {name: x, price: 1.0}\n", [_SAMPLE_PRODUCT])


def test_render_config_rejects_empty_labels():
    with pytest.raises(LabelTemplateError):
        render_config("page: {width_mm: 60, height_mm: 40}\nlabels: []\n", [_SAMPLE_PRODUCT])


def test_render_config_rejects_out_of_bounds_layout():
    template = (
        "page: {width_mm: 60, height_mm: 40}\n"
        "layout: {qr: {x_mm: 500, y_mm: 0, size_mm: 16}}\n"
        "labels:\n  - {name: x, price: 1.0}\n"
    )
    with pytest.raises(LabelTemplateError):
        render_config(template, [_SAMPLE_PRODUCT])


def test_render_label_sheet_produces_pdf():
    assert render_label_sheet(_sheet()).startswith(b"%PDF")


def test_render_label_sheet_page_count():
    pdf = render_label_sheet(_sheet(labels=[_label(), _label()]))
    assert b"/Count 2" in pdf


# ---- endpoints ------------------------------------------------------------

_PRODUCT = {
    "product_uid": "UID-1",
    "full_sku": "FULL-SKU-1",
    "sku": "SKU-1",
    "name": "Bolt",
    "set_name": "Double Masters",
    "price": 10.0,
    "quantity": 2,
}


def _create_product(client, **over):
    r = client.post("/products", json={**_PRODUCT, **over})
    assert r.status_code == 201
    return r.json()


def test_get_pdf_renders(client):
    _create_product(client)
    r = client.get("/labels/pdf", params={"ids": "1"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert "attachment" in r.headers["content-disposition"]


def test_get_pdf_one_label_per_quantity(client):
    _create_product(client)  # quantity 2
    r = client.get("/labels/pdf", params={"ids": "1"})
    assert b"/Count 2" in r.content


def test_get_pdf_missing_product_404(client):
    assert client.get("/labels/pdf", params={"ids": "99"}).status_code == 404


def test_get_pdf_bad_ids_422(client):
    assert client.get("/labels/pdf", params={"ids": "abc"}).status_code == 422


def test_get_pdf_unknown_template_404(client):
    _create_product(client)
    r = client.get("/labels/pdf", params={"ids": "1", "template_id": 999})
    assert r.status_code == 404


def test_post_pdf_inline_products(client):
    r = client.post("/labels/pdf", json={"products": [_PRODUCT]})
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


def test_post_pdf_rejects_template_and_id_together(client):
    r = client.post(
        "/labels/pdf", json={"products": [_PRODUCT], "template": "x: 1", "template_id": 1}
    )
    assert r.status_code == 422


def test_post_pdf_rejects_broken_template(client):
    r = client.post("/labels/pdf", json={"products": [_PRODUCT], "template": "{{ oops"})
    assert r.status_code == 422


def test_post_pdf_rejects_empty_products(client):
    assert client.post("/labels/pdf", json={"products": []}).status_code == 422


def test_save_rejects_out_of_bounds_layout(client):
    template = (
        "page: {width_mm: 60, height_mm: 40}\n"
        "layout: {qr: {x_mm: 500, y_mm: 0, size_mm: 16}}\n"
        "labels:\n  - {name: x, price: 1.0}\n"
    )
    r = client.post("/label-templates", json={"name": "bad", "template": template})
    assert r.status_code == 422
