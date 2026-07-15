from collections import Counter
from datetime import datetime, timedelta

from scout_backend.models.entities import ExecutionSignal, SignalKind, VerificationStatus

INVESTOR_LANGUAGE = {
    "company_value": "Is the company becoming more valuable?",
    "execution_acceleration": "Is execution accelerating?",
    "technical_risk": "Is technical risk decreasing?",
    "operational_maturity": "Is operational maturity improving?",
    "pmf_strength": "Is product-market fit getting stronger?",
    "investability": "Is the business becoming investable?",
}

CONNECTED_SOURCE_LABELS = {
    "github": "GitHub",
    "stripe": "Stripe",
    "aws": "AWS",
    "vercel": "Vercel",
    "hubspot": "HubSpot",
    "erp": "ERP",
}


def _recent(signals: list[ExecutionSignal], days: int = 30) -> list[ExecutionSignal]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    return [signal for signal in signals if signal.observed_at >= cutoff]


def _count_by_status(signals: list[ExecutionSignal]) -> Counter:
    counts = Counter(signal.verification_status.value for signal in signals)
    counts["pending"] = counts[VerificationStatus.attested.value] + counts[VerificationStatus.unverified.value]
    return counts


def _evidence_counts(signals: list[ExecutionSignal]) -> dict:
    counts = _count_by_status(signals)
    return {
        "verified": counts[VerificationStatus.verified.value],
        "attested": counts[VerificationStatus.attested.value],
        "self_reported": counts[VerificationStatus.self_reported.value],
        "inferred": counts[VerificationStatus.inferred.value],
        "unverified": counts[VerificationStatus.unverified.value],
        "pending": counts["pending"],
    }


def _metric(label: str, value: str, status: str, detail: str) -> dict:
    return {"label": label, "value": value, "status": status, "detail": detail}


def _confidence(signals: list[ExecutionSignal]) -> int:
    if not signals:
        return 0
    verified_weight = sum(1 for s in signals if s.verification_status == VerificationStatus.verified) * 100
    attested_weight = sum(1 for s in signals if s.verification_status == VerificationStatus.attested) * 70
    inferred_weight = sum(1 for s in signals if s.verification_status == VerificationStatus.inferred) * 60
    self_reported_weight = sum(1 for s in signals if s.verification_status == VerificationStatus.self_reported) * 30
    unverified_weight = sum(1 for s in signals if s.verification_status == VerificationStatus.unverified) * 10
    return round((verified_weight + attested_weight + inferred_weight + self_reported_weight + unverified_weight) / len(signals))


def _momentum(signals: list[ExecutionSignal]) -> tuple[str, str]:
    now = datetime.utcnow()
    last_7 = sum(1 for s in signals if s.observed_at >= now - timedelta(days=7))
    previous_7 = sum(1 for s in signals if now - timedelta(days=14) <= s.observed_at < now - timedelta(days=7))
    if last_7 > previous_7:
        return "Accelerating", f"{last_7} recent evidence item(s) vs {previous_7} in the previous period."
    if last_7 == previous_7 and last_7:
        return "Stable", f"{last_7} recent evidence item(s), matching the previous period."
    return "Needs evidence", "Scout needs more recent verified activity to detect momentum."


def _risk(signals: list[ExecutionSignal]) -> tuple[str, str]:
    recent = _recent(signals)
    verified = sum(1 for s in recent if s.verification_status == VerificationStatus.verified)
    self_reported = sum(1 for s in recent if s.verification_status == VerificationStatus.self_reported)
    if verified >= 5 and self_reported <= verified:
        return "Lower", "Multiple recent verified signals reduce diligence uncertainty."
    if verified:
        return "Moderate", "Some verified evidence exists, but more systems should be connected."
    return "High", "No recent verified evidence is connected yet."


def _investability(signals: list[ExecutionSignal]) -> tuple[str, str]:
    recent = _recent(signals)
    kinds = {signal.kind for signal in recent if signal.verification_status == VerificationStatus.verified}
    required = {SignalKind.product, SignalKind.customer, SignalKind.revenue, SignalKind.infrastructure}
    coverage = len(kinds & required)
    if coverage >= 3:
        return "Improving", "Verified evidence spans product, market, and operating dimensions."
    if coverage >= 1:
        return "Early", "Some investability evidence exists, but key business systems are missing."
    return "Unproven", "Connect customer, revenue, reliability, and product systems to prove investability."


def build_company_health(signals: list[ExecutionSignal]) -> dict:
    recent = _recent(signals)
    momentum, momentum_detail = _momentum(signals)
    risk, risk_detail = _risk(signals)
    investability, investability_detail = _investability(signals)
    confidence = _confidence(recent)
    last_updated = max((signal.observed_at for signal in signals), default=None)
    return {
        "momentum": _metric("Momentum", momentum, momentum.lower(), momentum_detail),
        "investability": _metric("Investability", investability, investability.lower(), investability_detail),
        "risk": _metric("Risk", risk, risk.lower(), risk_detail),
        "confidence": _metric("Confidence", f"{confidence}%", "evidence-weighted", "Confidence is weighted by provenance quality."),
        "evidence": _evidence_counts(recent),
        "last_updated": last_updated,
    }


def _timeline(signals: list[ExecutionSignal], limit: int = 8) -> list[dict]:
    recent = sorted(signals, key=lambda signal: signal.observed_at, reverse=True)[:limit]
    return [
        {
            "occurred_at": signal.observed_at,
            "title": f"{signal.name.replace('_', ' ')}: {signal.value:g} {signal.unit}",
            "why_it_matters": signal.investor_translation or "Raw execution evidence collected.",
            "verification_status": signal.verification_status.value,
        }
        for signal in recent
    ]


def _integration_items(signals: list[ExecutionSignal]) -> list[dict]:
    connected = {signal.source for signal in signals}
    return [
        _metric(label, "Connected" if source in connected else "Missing", "connected" if source in connected else "missing", "Evidence source available." if source in connected else "Connect this source to increase confidence.")
        for source, label in CONNECTED_SOURCE_LABELS.items()
    ]


def build_founder_dashboard(signals: list[ExecutionSignal]) -> dict:
    recent = _recent(signals)
    counts = _evidence_counts(recent)
    missing = sum(1 for item in _integration_items(signals) if item["status"] == "missing")
    return {
        "goal": "Help me prove progress.",
        "company_health": build_company_health(signals),
        "overview": {
            "title": "Overview",
            "items": [
                _metric("Execution health", f"{len(recent)} recent facts", "active" if recent else "needs_evidence", "Recent raw execution evidence collected."),
                _metric("Evidence collected", str(sum(counts.values()) - counts["pending"]), "tracked", "Verified, inferred, self-reported, and attested facts in the evidence ledger."),
                _metric("Momentum", build_company_health(signals)["momentum"]["value"], "trend", build_company_health(signals)["momentum"]["detail"]),
                build_company_health(signals)["confidence"],
            ],
        },
        "evidence": {
            "title": "Evidence",
            "items": [
                _metric("Verified evidence", str(counts["verified"]), "verified", "Collected directly from connected systems."),
                _metric("Pending verification", str(counts["pending"]), "pending", "Attested or unverified evidence needing stronger support."),
                _metric("Missing evidence", str(missing), "missing", "Important integrations not connected yet."),
            ],
        },
        "integrations": {"title": "Integrations", "items": _integration_items(signals)},
        "company_timeline": _timeline(signals),
        "investor_view_preview": "Preview the investor dashboard to see what claims are verified, weak, or missing.",
        "reports": ["Due diligence report", "Monthly investor update", "Shareable execution report"],
    }


def build_investor_dashboard(signals: list[ExecutionSignal]) -> dict:
    health = build_company_health(signals)
    recent = _recent(signals)
    kinds = Counter(signal.kind.value for signal in recent)
    ai_summary = (
        "Scout has not collected enough verified evidence to summarize company progress."
        if not recent
        else f"This company has {len(recent)} recent evidence item(s), {health['evidence']['verified']} verified. "
        f"Momentum is {health['momentum']['value'].lower()}, investability is {health['investability']['value'].lower()}, and risk is {health['risk']['value'].lower()}."
    )
    return {
        "goal": "Help me understand this company in 2 minutes.",
        "company_health": health,
        "company_summary": {
            "title": "Company Summary",
            "items": [health["momentum"], health["investability"], health["risk"], health["confidence"]],
        },
        "live_execution": {
            "title": "Live Execution",
            "items": [
                _metric("Product progress", str(kinds[SignalKind.product.value]), "evidence", "Product delivery evidence collected."),
                _metric("Customer growth", str(kinds[SignalKind.customer.value]), "evidence", "Customer adoption evidence collected."),
                _metric("Revenue quality", str(kinds[SignalKind.revenue.value]), "evidence", "Revenue evidence collected."),
                _metric("Infrastructure", str(kinds[SignalKind.infrastructure.value]), "evidence", "Reliability and infrastructure evidence collected."),
            ],
        },
        "timeline": _timeline(signals, limit=6),
        "risks": {
            "title": "Risks",
            "items": [
                _metric("Technical risk", health["risk"]["value"], health["risk"]["status"], health["risk"]["detail"]),
                _metric("Operational risk", "Unknown" if not kinds[SignalKind.operations.value] else "Tracked", "needs_evidence", "Connect operating systems for stronger operational-risk evidence."),
                _metric("Customer risk", "Unknown" if not kinds[SignalKind.customer.value] else "Tracked", "needs_evidence", "Connect analytics, CRM, and retention sources."),
                _metric("Financial risk", "Unknown" if not kinds[SignalKind.revenue.value] else "Tracked", "needs_evidence", "Connect revenue, banking, payroll, and burn data."),
            ],
        },
        "evidence": health["evidence"],
        "ai_summary": ai_summary,
        "due_diligence": {
            "title": "Due Diligence",
            "items": [
                _metric("Security", "Missing" if not kinds[SignalKind.compliance.value] else "Tracked", "needs_evidence", "Connect compliance and security systems."),
                _metric("Infrastructure", str(kinds[SignalKind.infrastructure.value]), "evidence", "Reliability data available."),
                _metric("Customers", str(kinds[SignalKind.customer.value]), "evidence", "Customer evidence available."),
                _metric("Compliance", str(kinds[SignalKind.compliance.value]), "evidence", "Compliance evidence available."),
                _metric("Manufacturing", str(kinds[SignalKind.manufacturing.value]), "evidence", "Manufacturing evidence available."),
                _metric("Product", str(kinds[SignalKind.product.value]), "evidence", "Product evidence available."),
            ],
        },
    }
