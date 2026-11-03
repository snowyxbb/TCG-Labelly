def _template_text(width_mm: int = 60) -> str:
    """A minimal template that satisfies the label-sheet contract."""
    return (
        "page:\n"
        f"  width_mm: {width_mm}\n"
        "  height_mm: 40\n"
        "labels:\n"
        "{% for p in products %}\n"
        "  - name: {{ p.name | y }}\n"
        "    price: {{ p.price | y }}\n"
        "{% endfor %}"
    )


def _payload(**overrides):
    data = {
        "name": "A4 two-column",
        "template": _template_text(),
        "description": "standard sheet",
    }
    data.update(overrides)
    return data


def test_create_and_get_template(client):
    r = client.post("/label-templates", json=_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1
    assert body["name"] == "A4 two-column"

    r = client.get("/label-templates/1")
    assert r.status_code == 200
    assert r.json()["template"].startswith("page:")


def test_list_templates(client):
    client.post("/label-templates", json=_payload())
    client.post("/label-templates", json=_payload(name="Letter wide"))
    r = client.get("/label-templates")
    assert r.status_code == 200
    assert [t["name"] for t in r.json()] == ["A4 two-column", "Letter wide"]


def test_create_rejects_duplicate_name(client):
    client.post("/label-templates", json=_payload())
    r = client.post("/label-templates", json=_payload(template=_template_text(50)))
    assert r.status_code == 409


def test_create_rejects_bad_jinja_syntax(client):
    r = client.post("/label-templates", json=_payload(template="{% for %}"))
    assert r.status_code == 422


def test_create_rejects_blank_fields(client):
    assert client.post("/label-templates", json=_payload(name="")).status_code == 422
    assert client.post("/label-templates", json=_payload(template="")).status_code == 422


def test_patch_updates_template_and_timestamp(client):
    client.post("/label-templates", json=_payload())
    created = client.get("/label-templates/1").json()
    r = client.patch("/label-templates/1", json={"template": _template_text(50), "name": "renamed"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "renamed"
    assert body["template"] == _template_text(50)
    assert body["updated_at"] >= created["updated_at"]


def test_patch_missing_returns_404(client):
    assert client.patch("/label-templates/999", json={"name": "x"}).status_code == 404


def test_delete_then_get_404(client):
    client.post("/label-templates", json=_payload())
    assert client.delete("/label-templates/1").status_code == 204
    assert client.get("/label-templates/1").status_code == 404


def test_search_by_partial_name(client):
    client.post("/label-templates", json=_payload())
    r = client.get("/label-templates/search", params={"q": "column"})
    assert r.status_code == 200
    assert [t["name"] for t in r.json()] == ["A4 two-column"]


def test_search_by_description(client):
    client.post("/label-templates", json=_payload())
    r = client.get("/label-templates/search", params={"q": "standard"})
    assert [t["name"] for t in r.json()] == ["A4 two-column"]


def test_search_is_case_insensitive(client):
    client.post("/label-templates", json=_payload())
    r = client.get("/label-templates/search", params={"q": "TWO-COLUMN"})
    assert [t["name"] for t in r.json()] == ["A4 two-column"]


def test_search_no_match_returns_empty_list(client):
    client.post("/label-templates", json=_payload())
    r = client.get("/label-templates/search", params={"q": "nonexistent"})
    assert r.status_code == 200
    assert r.json() == []


def test_search_requires_q(client):
    assert client.get("/label-templates/search").status_code == 422


def test_download_template_file(client):
    client.post("/label-templates", json=_payload())
    r = client.get("/label-templates/1/file")
    assert r.status_code == 200
    assert r.text.startswith("page:")
    assert r.headers["content-type"] == "application/x-yaml"
    assert "attachment" in r.headers["content-disposition"]
    assert "A4_two-column.yaml" in r.headers["content-disposition"]


def test_file_roundtrip(client):
    client.post("/label-templates", json=_payload())
    original = client.get("/label-templates/1/file").text
    edited = original.replace("width_mm: 60", "width_mm: 50")
    r = client.put(
        "/label-templates/1/file", content=edited.encode(), headers={"Content-Type": "text/yaml"}
    )
    assert r.status_code == 200
    assert client.get("/label-templates/1/file").text == edited


def test_upload_rejects_bad_syntax(client):
    client.post("/label-templates", json=_payload())
    assert client.put("/label-templates/1/file", content=b"{% for %}").status_code == 422


def test_upload_rejects_empty_body(client):
    client.post("/label-templates", json=_payload())
    assert client.put("/label-templates/1/file", content=b"").status_code == 422


def test_file_routes_missing_404(client):
    assert client.get("/label-templates/999/file").status_code == 404
    assert client.put("/label-templates/999/file", content=b"x: 1").status_code == 404


def test_download_default_template(client):
    r = client.get("/labels/template")
    assert r.status_code == 200
    assert "page:" in r.text
    assert r.headers["content-type"] == "application/x-yaml"


def test_create_from_file_roundtrip_with_default(client):
    """The user story: download the sample, upload it back as a new template."""
    sample = client.get("/labels/template").text
    r = client.post(
        "/label-templates/file",
        params={"name": "My First Template"},
        content=sample.encode(),
        headers={"Content-Type": "application/x-yaml"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "My First Template"
    assert body["template"] == sample
    assert client.get(f"/label-templates/{body['id']}/file").text == sample


def test_create_from_file_duplicate_name_409(client):
    sample = client.get("/labels/template").text
    client.post("/label-templates/file", params={"name": "dup"}, content=sample.encode())
    r = client.post("/label-templates/file", params={"name": "dup"}, content=sample.encode())
    assert r.status_code == 409


def test_create_from_file_rejects_invalid_yaml_render(client):
    # valid Jinja2, but renders to broken YAML (bad indentation)
    r = client.post(
        "/label-templates/file",
        params={"name": "broken"},
        content=b"x: {{ p.name | y }}\n  oops: 2",
    )
    assert r.status_code == 422


def test_create_from_file_rejects_unknown_field(client):
    r = client.post(
        "/label-templates/file",
        params={"name": "unknown-field"},
        content=b"name: {{ p.foil | y }}",
    )
    assert r.status_code == 422


def test_create_from_file_rejects_ssti(client):
    r = client.post(
        "/label-templates/file",
        params={"name": "ssti"},
        content=b"x: {{ ''.__class__ }}",
    )
    assert r.status_code == 422


def test_create_from_file_rejects_empty(client):
    r = client.post("/label-templates/file", params={"name": "empty"}, content=b"")
    assert r.status_code == 422
