def test_debug_models_requires_login(client):
    r = client.get("/api/debug/models")
    assert r.status_code == 401


def test_debug_models_returns_12_entries_when_logged_in(authed_client):
    r = authed_client.get("/api/debug/models")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 12
    slots = {row["slot"] for row in body}
    assert "extractor" in slots
    assert "manager" in slots
