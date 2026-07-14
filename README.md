# Scout Backend

Scout is an execution intelligence API for startups and investors. It creates startup workspaces, supports custom signal ingestion, stores provenance for every raw execution fact, and translates verified operational metadata into investor-readable evidence areas.

## Trust model

Scout should primarily rely on permissioned connectors and webhooks from systems such as GitHub, GitLab, Linear, Jira, Stripe, AWS, Vercel, Datadog, Shopify, HubSpot, and ERP/manufacturing tools. The custom API is useful for internal or uncommon systems, but self-reported data is lower confidence than data collected directly from a connected source.

Scout analyzes authorized operational metadata and never ingests proprietary source-code contents, CAD files, formulas, or design documents unless explicitly permitted. This is metadata-only collection, not cryptographic zero-knowledge proof.

## Provenance levels

Every signal records where it came from and how much investors should trust it:

- `verified`: collected directly from an integrated system.
- `attested`: submitted and signed by the company.
- `self_reported`: manually submitted or sent through the custom API.
- `inferred`: calculated by Scout from underlying evidence.
- `unverified`: insufficient supporting evidence.

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
uvicorn scout_backend.main:app --reload
```

## Core flow

1. `POST /v1/startups` creates the startup profile and returns a one-time API key for server-side integrations only.
2. Startups connect trusted systems through connectors/webhooks where possible.
3. Custom systems can send raw facts to `POST /v1/signals` with `Authorization: Bearer <api-key>`.
4. `POST /v1/connectors/github/public-repository` ingests limited verified GitHub metadata without reading source file contents; GitHub activity is treated as engineering/product-delivery context, not proof of business progress.
5. Founders read `GET /v1/founder-dashboard` to see how to prove progress, missing evidence, integrations, timeline, and report options.
6. Investors read `GET /v1/investor-dashboard` to understand company health, investability, risk, live execution, evidence, and diligence in two minutes.
7. Investors or founders can also read `GET /v1/investor-report` to see investor question answers, evidence areas, provenance mix, summaries, and limitations.
8. `GET /v1/execution-narrative` explains what the evidence means with conclusions, confidence, reasoning, limitations, and evidence references.
9. `GET /v1/evidence-timeline` shows the company evolution as a chronological evidence trail.

## Raw fact example

Send facts, not conclusions. Prefer `unit_manufacturing_cost` over `unit_cost_reduction`; Scout should calculate changes from the evidence ledger.

```json
{
  "kind": "manufacturing",
  "source": "erp",
  "name": "unit_manufacturing_cost",
  "value": 9,
  "unit": "USD",
  "verification_status": "verified",
  "source_event_id": "erp_event_29382",
  "observed_at": "2026-07-14T12:00:00Z"
}
```


## Investor questions Scout should answer

Scout is positioned as an execution evidence layer, not a GitHub analytics dashboard. The report is designed around investor questions such as:

- Is the product becoming more complete?
- Is technical debt increasing or decreasing?
- Is engineering velocity accelerating without breaking stability?
- Are customers actually using new features?
- Is infrastructure becoming more reliable?
- Is the company getting closer to product-market fit?

GitHub can support some product-delivery evidence, but business progress requires other connected systems such as product analytics, Stripe, CRM, infrastructure monitoring, support systems, payroll, banking, ERP, and manufacturing tools.


## Dashboard split

Scout exposes two different company dashboards because founders and investors have different jobs.

### Founder dashboard

Endpoint: `GET /v1/founder-dashboard`

Goal: **Help me prove progress.**

Includes execution health, evidence collected, momentum, confidence, verified evidence, pending verification, missing evidence, integrations, company timeline, investor-view preview, and report options.

### Investor dashboard

Endpoint: `GET /v1/investor-dashboard`

Goal: **Help me understand this company in 2 minutes.**

Includes company health, momentum, investability, risk, confidence, live execution, timeline, technical/operational/customer/financial risks, evidence counts, AI summary, and due diligence sections.

The dashboard language is intentionally company-focused rather than engineering-focused. Scout should answer whether the company is becoming more valuable, whether execution is accelerating, whether technical risk is decreasing, whether operational maturity is improving, whether product-market fit is getting stronger, and whether the business is becoming investable.


## Reasoning layer

Scout now separates four layers:

1. **Connect**: integrations and custom ingestion collect operational metadata.
2. **Evidence**: raw facts are stored with source, provenance, timeline, and verification status.
3. **Reasoning**: Scout interprets relationships between evidence, detects trajectory, identifies risks, and explains limitations.
4. **Investor intelligence**: Scout generates execution narrative, company outlook, diligence answers, timeline, dashboards, and reports.

The reasoning API is intentionally inspectable. Every insight includes the conclusion, confidence, reasoning, evidence references, and limitations so investors can audit why Scout said something.

## SOC 2-ready architecture notes

Scout is not SOC 2 certified by this scaffold, but the backend is moving toward SOC 2-ready controls:

- Data minimization: source code, CAD files, formulas, and documents are not collected by default.
- Provenance: every execution signal records source, verification status, source event ID, and observed time.
- Auditability: startup creation, signal ingestion, connector ingestion, report views, dashboard views, narrative views, timeline views, and security inventory views are audit logged.
- Inspectability: reasoning outputs include evidence references and limitations.
- API key safety: generated keys are returned once and stored only as hashes.

Security endpoints:

- `GET /v1/security/audit-logs` returns the latest audit trail for the authenticated startup.
- `GET /v1/security/data-inventory` returns Scout's current data-minimization and storage inventory.

## Deploy on Railway

1. Create a Railway project from this repository.
2. Add a Railway Postgres database if you do not want SQLite.
3. Railway will expose `DATABASE_URL`; the backend accepts either `DATABASE_URL` or `SCOUT_DATABASE_URL`.
4. Deploy with the included `Dockerfile` and `railway.json`.
5. Railway will set `PORT`; the container starts Uvicorn using that port.
6. Open `https://<your-railway-domain>/health` to confirm the API is running.
7. Create your first startup and API key:

```bash
curl -X POST "https://<your-railway-domain>/v1/startups" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Robotics","type":"hybrid"}'
```

8. Use the returned API key from a secure backend/CI/server-side environment:

```bash
curl "https://<your-railway-domain>/v1/security/data-inventory" \
  -H "Authorization: Bearer <scout_api_key>"
```
