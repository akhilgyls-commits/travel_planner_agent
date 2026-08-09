def test_health_check(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app_name"]
    assert "llm_provider" in body
    assert isinstance(body["mock_apis"], bool)


def test_root_endpoint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "docs" in body
    assert "health" in body
