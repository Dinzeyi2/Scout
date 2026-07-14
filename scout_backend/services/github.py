from datetime import datetime, timezone
import httpx

from scout_backend.core.config import get_settings
from scout_backend.models.entities import SignalKind


def _parse_github_time(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)


async def fetch_public_repo_signals(owner: str, repo: str) -> list[dict]:
    """Collect limited GitHub operational metadata; never treats activity counts as business proof."""
    base = f"https://api.github.com/repos/{owner}/{repo}"
    timeout = get_settings().github_timeout_seconds
    observed_at = datetime.utcnow()
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Scout-Backend"},
    ) as client:
        repo_resp = await client.get(base)
        repo_resp.raise_for_status()
        repo_data = repo_resp.json()

        releases_resp = await client.get(f"{base}/releases", params={"per_page": 10})
        releases_resp.raise_for_status()
        releases = releases_resp.json()

        deployments_resp = await client.get(f"{base}/deployments", params={"per_page": 10})
        deployments_count = len(deployments_resp.json()) if deployments_resp.status_code == 200 else 0

    pushed_at = _parse_github_time(repo_data.get("pushed_at"))
    latest_release = releases[0] if releases else None
    signals = [
        {
            "kind": SignalKind.engineering,
            "source": "github",
            "name": "repository_recently_updated",
            "value": 1.0,
            "unit": "boolean",
            "occurred_at": pushed_at,
            "observed_at": observed_at,
            "metadata": {
                "owner": owner,
                "repo": repo,
                "source_event_id": f"github:{owner}/{repo}:pushed_at:{repo_data.get('pushed_at')}",
                "limitation": "Repository updates indicate engineering activity, not business traction.",
            },
        },
        {
            "kind": SignalKind.product,
            "source": "github",
            "name": "recent_release_count",
            "value": float(len(releases)),
            "unit": "releases",
            "occurred_at": _parse_github_time(latest_release.get("published_at")) if latest_release else observed_at,
            "observed_at": observed_at,
            "metadata": {
                "owner": owner,
                "repo": repo,
                "source_event_id": f"github:{owner}/{repo}:releases",
                "limitation": "Releases suggest product delivery, but customer adoption must come from usage/revenue systems.",
            },
        },
    ]
    if deployments_count:
        signals.append(
            {
                "kind": SignalKind.infrastructure,
                "source": "github",
                "name": "recent_deployment_count",
                "value": float(deployments_count),
                "unit": "deployments",
                "occurred_at": observed_at,
                "observed_at": observed_at,
                "metadata": {
                    "owner": owner,
                    "repo": repo,
                    "source_event_id": f"github:{owner}/{repo}:deployments",
                    "limitation": "Deployment count needs CI/CD outcome, uptime, latency, and incident data for reliability conclusions.",
                },
            }
        )
    return signals
