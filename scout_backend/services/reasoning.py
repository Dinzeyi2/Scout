from datetime import datetime, timedelta

from scout_backend.models.entities import ExecutionSignal, SignalKind, VerificationStatus

TRUSTED_STATUSES = {VerificationStatus.verified, VerificationStatus.attested, VerificationStatus.inferred}


def _recent(signals: list[ExecutionSignal], days: int = 60) -> list[ExecutionSignal]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    return [signal for signal in signals if signal.observed_at >= cutoff]


def _refs(signals: list[ExecutionSignal]) -> list[dict]:
    return [
        {
            "signal_id": signal.id,
            "name": signal.name,
            "source": signal.source,
            "verification_status": signal.verification_status.value,
            "observed_at": signal.observed_at,
        }
        for signal in signals
    ]


def _confidence(signals: list[ExecutionSignal]) -> str:
    if not signals:
        return "low"
    verified = sum(1 for signal in signals if signal.verification_status == VerificationStatus.verified)
    trusted = sum(1 for signal in signals if signal.verification_status in TRUSTED_STATUSES)
    if verified >= 3 and trusted == len(signals):
        return "high"
    if verified >= 1 or trusted >= 2:
        return "medium"
    return "low"


def _kind(signals: list[ExecutionSignal], kind: SignalKind) -> list[ExecutionSignal]:
    return [signal for signal in signals if signal.kind == kind]


def _trend(signals: list[ExecutionSignal]) -> str:
    now = datetime.utcnow()
    last_30 = sum(1 for signal in signals if signal.observed_at >= now - timedelta(days=30))
    previous_30 = sum(1 for signal in signals if now - timedelta(days=60) <= signal.observed_at < now - timedelta(days=30))
    if last_30 > previous_30:
        return "Accelerating"
    if last_30 == previous_30 and last_30:
        return "Stable"
    return "Unproven"


def _latest_value(signals: list[ExecutionSignal], name_contains: str) -> ExecutionSignal | None:
    matches = [signal for signal in signals if name_contains in signal.name]
    return max(matches, key=lambda signal: signal.observed_at, default=None)


def _build_insight(title: str, conclusion: str, reasoning: str, evidence: list[ExecutionSignal], limitations: list[str]) -> dict:
    return {
        "title": title,
        "conclusion": conclusion,
        "confidence": _confidence(evidence),
        "reasoning": reasoning,
        "evidence": _refs(evidence),
        "limitations": limitations,
    }


def build_execution_narrative(signals: list[ExecutionSignal]) -> dict:
    recent = _recent(signals)
    product = _kind(recent, SignalKind.product)
    customer = _kind(recent, SignalKind.customer)
    revenue = _kind(recent, SignalKind.revenue)
    infrastructure = _kind(recent, SignalKind.infrastructure)
    operations = _kind(recent, SignalKind.operations)
    manufacturing = _kind(recent, SignalKind.manufacturing)
    compliance = _kind(recent, SignalKind.compliance)

    momentum = _trend(recent)
    evidence_confidence = _confidence(recent)
    product_maturity = "Growing" if product else "Unproven"
    customer_adoption = "Strengthening" if customer or revenue else "Unproven"
    operational_risk = "Lower" if infrastructure and operations else "Needs evidence"
    next_milestone = _next_milestone(product, customer, revenue, infrastructure, manufacturing, compliance)

    insights = [
        _build_insight(
            "Investability trajectory",
            _investability_conclusion(product, customer, revenue, infrastructure),
            "Scout compares verified evidence across product, customer, revenue, and reliability dimensions instead of relying on isolated activity metrics.",
            (product + customer + revenue + infrastructure)[-8:],
            _missing_sources(product, customer, revenue, infrastructure),
        ),
        _build_insight(
            "Execution acceleration",
            f"Execution momentum is {momentum.lower()} based on the last 60 days of evidence.",
            "Scout compares recent evidence frequency against the previous period and requires provenance before treating acceleration as meaningful.",
            recent[-8:],
            ["Frequency alone does not prove quality; connect customer, incident, and financial systems to validate outcomes."],
        ),
        _build_insight(
            "Risk movement",
            _risk_conclusion(infrastructure, operations, compliance),
            "Scout looks for reliability, operational, and compliance evidence because investors care whether execution risk is decreasing as the company scales.",
            (infrastructure + operations + compliance)[-8:],
            _missing_risk_sources(infrastructure, operations, compliance),
        ),
    ]

    narrative = _narrative_text(momentum, evidence_confidence, product, customer, revenue, infrastructure, operations)
    return {
        "company_outlook": {
            "momentum": momentum,
            "confidence": evidence_confidence.capitalize(),
            "product_maturity": product_maturity,
            "operational_risk": operational_risk,
            "customer_adoption": customer_adoption,
            "next_milestone": next_milestone,
        },
        "narrative": narrative,
        "insights": insights,
        "methodology": [
            "Every conclusion links back to evidence references with source and verification status.",
            "Verified connector data is weighted above attested, inferred, self-reported, and unverified data.",
            "Scout separates evidence collection from interpretation so investors can inspect the facts behind each claim.",
            "Scout avoids claiming business progress from engineering activity unless customer, revenue, reliability, or operating evidence supports it.",
        ],
    }


def _investability_conclusion(
    product: list[ExecutionSignal],
    customer: list[ExecutionSignal],
    revenue: list[ExecutionSignal],
    infrastructure: list[ExecutionSignal],
) -> str:
    dimensions = sum(bool(items) for items in [product, customer, revenue, infrastructure])
    if dimensions >= 3:
        return "The business is becoming more investable because evidence spans product delivery, market response, and operating reliability."
    if dimensions >= 2:
        return "Investability is forming, but Scout needs more verified customer, revenue, and reliability evidence before making a strong conclusion."
    return "Investability is not yet proven; Scout needs connected evidence beyond isolated activity."


def _risk_conclusion(
    infrastructure: list[ExecutionSignal], operations: list[ExecutionSignal], compliance: list[ExecutionSignal]
) -> str:
    if infrastructure and operations and compliance:
        return "Execution risk appears to be decreasing because reliability, operating, and compliance evidence are all present."
    if infrastructure:
        return "Technical risk may be improving, but operational and compliance evidence are still incomplete."
    return "Technical and operational risk remain unproven because reliability and operating evidence are missing."


def _missing_sources(
    product: list[ExecutionSignal],
    customer: list[ExecutionSignal],
    revenue: list[ExecutionSignal],
    infrastructure: list[ExecutionSignal],
) -> list[str]:
    missing = []
    if not product:
        missing.append("Connect product delivery systems such as Linear, Jira, GitHub releases, or deployment records.")
    if not customer:
        missing.append("Connect product analytics, CRM, or customer-success systems to prove customer adoption.")
    if not revenue:
        missing.append("Connect Stripe, billing, banking, or finance systems to prove revenue quality.")
    if not infrastructure:
        missing.append("Connect uptime, incident, Sentry, Datadog, AWS, or Vercel data to prove reliability.")
    return missing or ["Continue validating this interpretation against customer outcomes and future financing events."]


def _missing_risk_sources(
    infrastructure: list[ExecutionSignal], operations: list[ExecutionSignal], compliance: list[ExecutionSignal]
) -> list[str]:
    missing = []
    if not infrastructure:
        missing.append("Missing reliability evidence from monitoring, incidents, latency, uptime, or deployment health.")
    if not operations:
        missing.append("Missing operational evidence such as support load, hiring, burn, payroll, or cost efficiency.")
    if not compliance:
        missing.append("Missing compliance/security evidence such as SOC 2, FDA, CE, privacy, or audit milestones.")
    return missing or ["Risk interpretation should still be validated against incidents and customer impact."]


def _next_milestone(
    product: list[ExecutionSignal],
    customer: list[ExecutionSignal],
    revenue: list[ExecutionSignal],
    infrastructure: list[ExecutionSignal],
    manufacturing: list[ExecutionSignal],
    compliance: list[ExecutionSignal],
) -> str:
    if product and not customer:
        return "Prove customer usage of shipped product"
    if customer and not revenue:
        return "Convert adoption into revenue quality"
    if revenue and not infrastructure:
        return "Prove reliability while revenue grows"
    if manufacturing and not compliance:
        return "Validate manufacturing progress with compliance milestones"
    return "Connect more systems to identify the next investability milestone"


def _narrative_text(
    momentum: str,
    confidence: str,
    product: list[ExecutionSignal],
    customer: list[ExecutionSignal],
    revenue: list[ExecutionSignal],
    infrastructure: list[ExecutionSignal],
    operations: list[ExecutionSignal],
) -> str:
    pieces = [f"Momentum is {momentum.lower()} with {confidence} confidence."]
    if product:
        pieces.append("Product maturity is showing evidence of progress.")
    if customer or revenue:
        pieces.append("Market evidence is present through customer or revenue signals.")
    if infrastructure and operations:
        pieces.append("Operating maturity is improving because reliability and operational evidence are both present.")
    if not (customer or revenue):
        pieces.append("Product-market-fit strength remains unproven until customer usage or revenue systems are connected.")
    return " ".join(pieces)


def build_evidence_timeline(signals: list[ExecutionSignal]) -> dict:
    ordered = sorted(signals, key=lambda signal: signal.observed_at)
    return {
        "events": [
            {
                "date": signal.observed_at,
                "title": signal.name.replace("_", " ").title(),
                "category": signal.kind.value,
                "why_it_matters": signal.investor_translation or _timeline_reason(signal),
                "verification_status": signal.verification_status.value,
                "source": signal.source,
                "signal_id": signal.id,
            }
            for signal in ordered
        ]
    }


def _timeline_reason(signal: ExecutionSignal) -> str:
    category_reasons = {
        SignalKind.product: "Product progress matters because investors need to know what has actually shipped.",
        SignalKind.customer: "Customer evidence matters because it indicates whether the market is responding.",
        SignalKind.revenue: "Revenue evidence matters because it shows whether adoption is becoming commercial value.",
        SignalKind.infrastructure: "Reliability evidence matters because execution risk should decline as usage grows.",
        SignalKind.manufacturing: "Manufacturing evidence matters because physical startups must prove they can scale production.",
        SignalKind.compliance: "Compliance evidence matters because regulatory readiness can unlock or block commercialization.",
    }
    return category_reasons.get(signal.kind, "This event adds to the company's execution history.")
