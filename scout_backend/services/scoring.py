from collections import Counter, defaultdict
from datetime import datetime, timedelta

from scout_backend.models.entities import ExecutionSignal, SignalKind, VerificationStatus

AREA_KIND_MAP = {
    "product_delivery": {SignalKind.product, SignalKind.engineering},
    "customer_adoption": {SignalKind.customer},
    "revenue_quality": {SignalKind.revenue},
    "reliability": {SignalKind.infrastructure},
    "capital_efficiency": {SignalKind.operations, SignalKind.revenue},
    "manufacturing_readiness": {SignalKind.manufacturing},
    "compliance_readiness": {SignalKind.compliance},
    "execution_consistency": set(SignalKind),
}

AREA_LABELS = {
    "product_delivery": "Product delivery",
    "customer_adoption": "Customer adoption",
    "revenue_quality": "Revenue quality",
    "reliability": "Reliability",
    "capital_efficiency": "Capital efficiency",
    "manufacturing_readiness": "Manufacturing readiness",
    "compliance_readiness": "Compliance readiness",
    "execution_consistency": "Execution consistency",
}


INVESTOR_QUESTIONS = [
    (
        "Is the product becoming more complete?",
        "product_delivery",
        ["GitHub/GitLab releases", "Linear/Jira shipped milestones", "production deployment records"],
    ),
    (
        "Is technical debt increasing or decreasing?",
        "reliability",
        ["CI results", "dependency health", "incident history", "test health"],
    ),
    (
        "Is engineering velocity accelerating without breaking stability?",
        "execution_consistency",
        ["deployments", "cycle time", "change failure rate", "rollback data"],
    ),
    (
        "Are customers actually using new features?",
        "customer_adoption",
        ["PostHog/analytics events", "Stripe", "CRM", "product usage telemetry"],
    ),
    (
        "Is infrastructure becoming more reliable?",
        "reliability",
        ["Datadog/Sentry", "uptime checks", "latency metrics", "incident logs"],
    ),
    (
        "Is the company getting closer to product-market fit?",
        "customer_adoption",
        ["retention", "expansion revenue", "activation", "customer interviews", "usage cohorts"],
    ),
]

VERIFICATION_WEIGHT = {
    VerificationStatus.verified: 1.0,
    VerificationStatus.attested: 0.75,
    VerificationStatus.inferred: 0.65,
    VerificationStatus.self_reported: 0.35,
    VerificationStatus.unverified: 0.15,
}


def translate_signal(signal: ExecutionSignal | SignalKind, name: str | None = None, value: float | None = None, unit: str | None = None) -> str:
    if isinstance(signal, ExecutionSignal):
        kind = signal.kind
        name = signal.name
        value = signal.value
        unit = signal.unit
        status = signal.verification_status.value.replace("_", " ")
        source = signal.source
    else:
        kind = signal
        status = VerificationStatus.self_reported.value.replace("_", " ")
        source = "custom API"

    templates = {
        SignalKind.engineering: "{status} engineering fact from {source}: {name} measured {value:g} {unit}.",
        SignalKind.infrastructure: "{status} reliability fact from {source}: {name} measured {value:g} {unit}.",
        SignalKind.customer: "{status} customer adoption fact from {source}: {name} reached {value:g} {unit}.",
        SignalKind.manufacturing: "{status} manufacturing fact from {source}: {name} measured {value:g} {unit}.",
        SignalKind.compliance: "{status} compliance fact from {source}: {name} measured {value:g} {unit}.",
        SignalKind.revenue: "{status} revenue fact from {source}: {name} reached {value:g} {unit}.",
        SignalKind.product: "{status} product delivery fact from {source}: {name} measured {value:g} {unit}.",
        SignalKind.operations: "{status} operations fact from {source}: {name} measured {value:g} {unit}.",
    }
    return templates[kind].format(
        status=status.capitalize(), source=source, name=(name or "signal").replace("_", " "), value=value or 0, unit=unit or "count"
    )


def _bounded(score: float) -> int:
    return max(0, min(100, round(score)))


def _area_score(signals: list[ExecutionSignal]) -> int:
    if not signals:
        return 0
    weighted_activity = sum(VERIFICATION_WEIGHT[s.verification_status] for s in signals)
    verified_bonus = sum(1 for s in signals if s.verification_status == VerificationStatus.verified) * 4
    source_diversity = len({s.source for s in signals}) * 5
    return _bounded(20 + weighted_activity * 8 + verified_bonus + source_diversity)


def _limitations(signals: list[ExecutionSignal]) -> list[str]:
    if not signals:
        return ["No recent evidence connected for this area yet."]
    limitations: list[str] = []
    if not any(s.verification_status == VerificationStatus.verified for s in signals):
        limitations.append("No directly verified connector evidence yet; treat this area as lower confidence.")
    if len({s.source for s in signals}) == 1:
        limitations.append("Evidence comes from one source; additional connected systems would improve confidence.")
    if any(s.verification_status == VerificationStatus.self_reported for s in signals):
        limitations.append("Some evidence is self-reported through the custom ingestion API.")
    return limitations


def _build_area(key: str, signals: list[ExecutionSignal]) -> dict:
    verification_mix = Counter(s.verification_status.value for s in signals)
    evidence = [s.investor_translation or translate_signal(s) for s in signals[-5:]]
    summary = (
        f"{AREA_LABELS[key]} has {len(signals)} recent signal(s) across {len({s.source for s in signals})} source(s)."
        if signals
        else f"{AREA_LABELS[key]} has no recent connected evidence."
    )
    return {
        "name": AREA_LABELS[key],
        "score": _area_score(signals),
        "verification_mix": dict(verification_mix),
        "summary": summary,
        "evidence": evidence,
        "limitations": _limitations(signals),
    }



def _confidence(area: dict) -> str:
    if area["verification_mix"].get(VerificationStatus.verified.value, 0) >= 2 and area["score"] >= 50:
        return "medium"
    if area["verification_mix"].get(VerificationStatus.verified.value, 0) >= 1:
        return "early"
    return "low"


def _answer_question(question: str, area_key: str, required_sources: list[str], area: dict) -> dict:
    if not area["evidence"]:
        answer = "Insufficient evidence connected yet. Scout needs trusted source data before making this claim."
    elif area["verification_mix"].get(VerificationStatus.verified.value, 0):
        answer = f"Early evidence exists: {area['summary']} This is not yet a full business-progress conclusion."
    else:
        answer = f"Only lower-confidence evidence exists: {area['summary']} Verified connectors are needed before investors should rely on it."
    return {
        "question": question,
        "answer": answer,
        "confidence": _confidence(area),
        "required_sources": required_sources,
    }

def build_score(signals: list[ExecutionSignal]) -> dict:
    now = datetime.utcnow()
    recent = [s for s in signals if s.observed_at >= now - timedelta(days=30)]
    by_area: dict[str, list[ExecutionSignal]] = defaultdict(list)
    for signal in recent:
        for area, kinds in AREA_KIND_MAP.items():
            if signal.kind in kinds:
                by_area[area].append(signal)

    areas = {area: _build_area(area, by_area[area]) for area in AREA_KIND_MAP}
    areas["investor_questions"] = [
        _answer_question(question, area_key, required_sources, areas[area_key])
        for question, area_key, required_sources in INVESTOR_QUESTIONS
    ]
    verified_count = sum(1 for s in recent if s.verification_status == VerificationStatus.verified)
    self_reported_count = sum(1 for s in recent if s.verification_status == VerificationStatus.self_reported)
    areas["investor_summary"] = (
        f"Scout found {len(recent)} recent raw execution fact(s): {verified_count} verified by connected systems "
        f"and {self_reported_count} self-reported through custom ingestion. Reports should prioritize verified evidence."
    )
    areas["evidence"] = [s.investor_translation or translate_signal(s) for s in recent[-8:]]
    return areas
