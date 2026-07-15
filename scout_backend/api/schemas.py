from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

from scout_backend.models.entities import SignalKind, StartupType, VerificationStatus


class StartupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    type: StartupType = StartupType.software
    website: HttpUrl | None = None
    api_key_name: str = "default"


class StartupCreated(BaseModel):
    id: int
    name: str
    api_key: str
    api_key_prefix: str


class SignalIn(BaseModel):
    kind: SignalKind
    source: str = Field(min_length=1, max_length=80)
    name: str = Field(
        min_length=1,
        max_length=160,
        description="Raw fact name, not a founder-chosen conclusion. Example: unit_manufacturing_cost, not unit_cost_reduction.",
    )
    value: float
    unit: str = "count"
    occurred_at: datetime | None = None
    observed_at: datetime | None = None
    verification_status: VerificationStatus = VerificationStatus.self_reported
    source_event_id: str | None = Field(default=None, max_length=160)
    metadata: dict = Field(default_factory=dict)


class SignalOut(SignalIn):
    id: int
    investor_translation: str


class GitHubRepositoryIn(BaseModel):
    owner: str
    repo: str
    branch: str = "main"


class EvidenceArea(BaseModel):
    name: str
    score: int
    verification_mix: dict[str, int]
    summary: str
    evidence: list[str]
    limitations: list[str]


class InvestorQuestionAnswer(BaseModel):
    question: str
    answer: str
    confidence: str
    required_sources: list[str]


class ScoreOut(BaseModel):
    investor_questions: list[InvestorQuestionAnswer]
    product_delivery: EvidenceArea
    customer_adoption: EvidenceArea
    revenue_quality: EvidenceArea
    reliability: EvidenceArea
    capital_efficiency: EvidenceArea
    manufacturing_readiness: EvidenceArea
    compliance_readiness: EvidenceArea
    execution_consistency: EvidenceArea
    investor_summary: str
    evidence: list[str]


class HealthMetric(BaseModel):
    label: str
    value: str
    status: str
    detail: str


class EvidenceCounts(BaseModel):
    verified: int
    attested: int
    self_reported: int
    inferred: int
    unverified: int
    pending: int


class CompanyHealth(BaseModel):
    momentum: HealthMetric
    investability: HealthMetric
    risk: HealthMetric
    confidence: HealthMetric
    evidence: EvidenceCounts
    last_updated: datetime | None


class DashboardSection(BaseModel):
    title: str
    items: list[HealthMetric]


class TimelineItem(BaseModel):
    occurred_at: datetime
    title: str
    why_it_matters: str
    verification_status: str


class FounderDashboard(BaseModel):
    goal: str
    company_health: CompanyHealth
    overview: DashboardSection
    evidence: DashboardSection
    integrations: DashboardSection
    company_timeline: list[TimelineItem]
    investor_view_preview: str
    reports: list[str]


class InvestorDashboard(BaseModel):
    goal: str
    company_health: CompanyHealth
    company_summary: DashboardSection
    live_execution: DashboardSection
    timeline: list[TimelineItem]
    risks: DashboardSection
    evidence: EvidenceCounts
    ai_summary: str
    due_diligence: DashboardSection


class EvidenceReference(BaseModel):
    signal_id: int
    name: str
    source: str
    verification_status: str
    observed_at: datetime


class ReasonedInsight(BaseModel):
    title: str
    conclusion: str
    confidence: str
    reasoning: str
    evidence: list[EvidenceReference]
    limitations: list[str]


class CompanyOutlook(BaseModel):
    momentum: str
    confidence: str
    product_maturity: str
    operational_risk: str
    customer_adoption: str
    next_milestone: str


class ExecutionNarrative(BaseModel):
    company_outlook: CompanyOutlook
    narrative: str
    insights: list[ReasonedInsight]
    methodology: list[str]


class EvidenceTimelineEvent(BaseModel):
    date: datetime
    title: str
    category: str
    why_it_matters: str
    verification_status: str
    verification_badge: str
    badge_color: str
    trust_rank: int
    source: str
    signal_id: int


class EvidenceTimeline(BaseModel):
    events: list[EvidenceTimelineEvent]


class AuditLogOut(BaseModel):
    id: int
    action: str
    actor: str
    resource_type: str
    resource_id: str | None
    metadata: dict
    created_at: datetime


class DataInventoryItem(BaseModel):
    category: str
    stored: bool
    purpose: str
    default_collection: str
    retention: str


class SecurityInventory(BaseModel):
    data_minimization_policy: str
    source_code_default: str
    api_key_storage: str
    audit_logging: str
    data_inventory: list[DataInventoryItem]


class GitHubRepositoryUrlIn(BaseModel):
    repo_url: str
    branch: str = "main"


class IntegrationPanel(BaseModel):
    api_key_prefix: str | None
    warning: str
    environment_variables: dict[str, str]
    sdk_snippets: dict[str, str]
    recommended_connectors: list[dict[str, str]]

