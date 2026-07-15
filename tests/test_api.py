from fastapi.testclient import TestClient

from scout_backend.main import create_app
from scout_backend.models.database import Base, engine


def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestClient(create_app())


def test_startup_key_signal_and_report_flow():
    c = client()
    created = c.post("/v1/startups", json={"name": "Acme Robotics", "type": "hybrid"}).json()
    assert created["api_key"].startswith("scout_live_")

    headers = {"Authorization": f"Bearer {created['api_key']}"}
    signal = c.post(
        "/v1/signals",
        headers=headers,
        json={
            "kind": "manufacturing",
            "source": "erp",
            "name": "unit_manufacturing_cost",
            "value": 9,
            "unit": "USD",
            "verification_status": "verified",
            "source_event_id": "erp_event_29382",
        },
    )
    assert signal.status_code == 200
    body = signal.json()
    assert body["verification_status"] == "verified"
    assert body["source_event_id"] == "erp_event_29382"
    assert "Verified manufacturing fact" in body["investor_translation"]

    report = c.get("/v1/investor-report", headers=headers)
    assert report.status_code == 200
    assert report.json()["manufacturing_readiness"]["verification_mix"]["verified"] == 1
    assert report.json()["manufacturing_readiness"]["limitations"]
    assert report.json()["investor_questions"][0]["question"] == "Is the product becoming more complete?"

    founder_dashboard = c.get("/v1/founder-dashboard", headers=headers)
    assert founder_dashboard.status_code == 200
    assert founder_dashboard.json()["goal"] == "Help me prove progress."
    assert founder_dashboard.json()["company_health"]["evidence"]["verified"] == 1

    investor_dashboard = c.get("/v1/investor-dashboard", headers=headers)
    assert investor_dashboard.status_code == 200
    assert investor_dashboard.json()["goal"] == "Help me understand this company in 2 minutes."
    assert "investability" in investor_dashboard.json()["company_health"]

    narrative = c.get("/v1/execution-narrative", headers=headers)
    assert narrative.status_code == 200
    assert "company_outlook" in narrative.json()
    assert narrative.json()["insights"][0]["evidence"]

    timeline = c.get("/v1/evidence-timeline", headers=headers)
    assert timeline.status_code == 200
    assert timeline.json()["events"][0]["verification_status"] == "verified"
    assert timeline.json()["events"][0]["verification_badge"] == "✅ Verified"

    integration_panel = c.get("/v1/founder-integration-panel", headers=headers)
    assert integration_panel.status_code == 200
    assert integration_panel.json()["recommended_connectors"][0]["endpoint"] == "/v1/connectors/github/repository-url"
    assert "Scout.fromEnv" in integration_panel.json()["sdk_snippets"]["typescript"]

    inventory = c.get("/v1/security/data-inventory", headers=headers)
    assert inventory.status_code == 200
    assert inventory.json()["source_code_default"].startswith("Source code contents are not ingested")

    audit_logs = c.get("/v1/security/audit-logs", headers=headers)
    assert audit_logs.status_code == 200
    assert any(log["action"] == "signal_ingested" for log in audit_logs.json())


def test_self_reported_custom_signal_is_labeled_lower_confidence():
    c = client()
    created = c.post("/v1/startups", json={"name": "Acme SaaS"}).json()
    headers = {"Authorization": f"Bearer {created['api_key']}"}
    response = c.post(
        "/v1/signals",
        headers=headers,
        json={"kind": "revenue", "source": "custom_api", "name": "monthly_recurring_revenue", "value": 1000, "unit": "USD"},
    )
    assert response.status_code == 200
    assert response.json()["verification_status"] == "self_reported"

    report = c.get("/v1/investor-report", headers=headers).json()
    assert "self_reported" in report["revenue_quality"]["verification_mix"]
    assert "Some evidence is self-reported" in report["revenue_quality"]["limitations"][-1]


def test_requires_api_key_for_signals():
    c = client()
    response = c.post("/v1/signals", json={"kind": "engineering", "source": "ci", "name": "deploys", "value": 3})
    assert response.status_code == 401


def test_system_aliases_are_railway_friendly():
    c = client()
    assert c.get("/").status_code == 200
    assert c.get("/api").json()["api_prefix"] == "/v1"
    assert c.get("/api/health").json()["status"] == "ok"
    assert c.get("/status").json()["status"] == "ok"
    assert c.get("/ping").json()["status"] == "ok"
    assert c.get("/version").json()["version"] == "0.1.0"
