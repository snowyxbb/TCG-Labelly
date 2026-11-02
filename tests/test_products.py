def sample(**overrides):
    data = {
        "product_uid": "P-001",
        "full_sku": "2XM-123-EN",
        "sku": "2XM-123",
        "name": "Lightning Bolt",
        "set_name": "Double Masters",
        "price": 3.456,
    }
    data.update(overrides)
    return data


def test_create_rounds_price_and_applies_defaults(client):
    r = client.post("/products", json=sample())
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1
    assert body["price"] == 3.46  # 2dp invariant enforced at the write boundary
    assert body["language"] == "EN"
    assert body["currency"] == "SGD"
    assert body["is_active"] is True


def test_create_rejects_negative_price(client):
    r = client.post("/products", json=sample(price=-1))
    assert r.status_code == 422


def test_create_rejects_blank_required_fields(client):
    r = client.post("/products", json=sample(name=""))
    assert r.status_code == 422


def test_create_rejects_duplicate_uid(client):
    assert client.post("/products", json=sample()).status_code == 201
    r = client.post("/products", json=sample(full_sku="OTHER-SKU"))
    assert r.status_code == 409


def test_get_missing_returns_404(client):
    assert client.get("/products/999").status_code == 404


def test_list_filters_by_set_and_language(client):
    client.post("/products", json=sample())
    client.post(
        "/products",
        json=sample(
            product_uid="P-002",
            full_sku="2XM-124-JP",
            sku="2XM-124",
            name="Counterspell",
            language="JP",
        ),
    )
    r = client.get("/products", params={"set_name": "Double Masters", "language": "JP"})
    assert r.status_code == 200
    assert [p["name"] for p in r.json()] == ["Counterspell"]


def test_patch_updates_only_provided_fields(client):
    client.post("/products", json=sample())
    r = client.patch("/products/1", json={"price": 9.999, "on_sale": True})
    assert r.status_code == 200
    body = r.json()
    assert body["price"] == 10.0  # rounded
    assert body["on_sale"] is True
    assert body["name"] == "Lightning Bolt"  # untouched


def test_patch_missing_returns_404(client):
    assert client.patch("/products/999", json={"price": 1}).status_code == 404


def test_delete_then_get_404(client):
    client.post("/products", json=sample())
    assert client.delete("/products/1").status_code == 204
    assert client.get("/products/1").status_code == 404


def test_search_by_partial_name(client):
    client.post("/products", json=sample())
    r = client.get("/products/search", params={"q": "bolt"})
    assert r.status_code == 200
    assert [p["name"] for p in r.json()] == ["Lightning Bolt"]


def test_search_name_is_case_insensitive(client):
    client.post("/products", json=sample())
    r = client.get("/products/search", params={"q": "BOLT"})
    assert [p["name"] for p in r.json()] == ["Lightning Bolt"]


def test_search_by_each_identifier(client):
    client.post("/products", json=sample())
    for field, value in [
        ("sku", "2XM-123"),
        ("product_uid", "P-001"),
        ("full_sku", "2XM-123-EN"),
    ]:
        r = client.get("/products/search", params={"q": value})
        assert r.status_code == 200, field
        assert [p["sku"] for p in r.json()] == ["2XM-123"], field


def test_search_no_match_returns_empty_list(client):
    client.post("/products", json=sample())
    r = client.get("/products/search", params={"q": "nonexistent"})
    assert r.status_code == 200
    assert r.json() == []


def test_search_requires_q(client):
    assert client.get("/products/search").status_code == 422


def test_sale_endpoint_toggles_and_sets_discount(client):
    client.post("/products", json=sample())
    r = client.patch("/products/1/sale", json={"on_sale": True, "discount": 20})
    assert r.status_code == 200
    body = r.json()
    assert body["on_sale"] is True
    assert body["discount"] == 20.0

    r = client.patch("/products/1/sale", json={"on_sale": False})
    body = r.json()
    assert body["on_sale"] is False
    assert body["discount"] == 20.0  # value kept for next time


def test_sale_endpoint_rejects_out_of_range_discount(client):
    client.post("/products", json=sample())
    assert client.patch("/products/1/sale", json={"discount": 150}).status_code == 422
    assert client.patch("/products/1/sale", json={"discount": -1}).status_code == 422


def test_sale_endpoint_rejects_empty_body(client):
    client.post("/products", json=sample())
    assert client.patch("/products/1/sale", json={}).status_code == 422


def test_sale_endpoint_missing_product_404(client):
    assert client.patch("/products/999/sale", json={"on_sale": True}).status_code == 404


def test_create_and_patch_accept_discount(client):
    r = client.post("/products", json=sample(discount=15))
    assert r.json()["discount"] == 15.0
    r = client.patch("/products/1", json={"discount": 30})
    assert r.json()["discount"] == 30.0
