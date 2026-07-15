from urllib.parse import urlparse


def parse_github_repo_url(repo_url: str) -> tuple[str, str]:
    cleaned = repo_url.strip().removesuffix(".git")
    if cleaned.startswith("git@github.com:"):
        path = cleaned.removeprefix("git@github.com:")
    else:
        parsed = urlparse(cleaned)
        if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            raise ValueError("Only github.com repository URLs are supported.")
        path = parsed.path.strip("/")
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("GitHub repository URL must include owner and repo.")
    return parts[0], parts[1]


def founder_sdk_snippets(base_url: str) -> dict[str, str]:
    return {
        "typescript": (
            'import { Scout } from "@scout/execution";\n'
            "const scout = Scout.fromEnv();\n"
            'await scout.track({ kind: "revenue", source: "stripe", name: "monthly_recurring_revenue", value: 12000, unit: "USD", verification_status: "verified" });'
        ),
        "python": (
            "from scout_execution import Scout\n"
            "scout = Scout.from_env()\n"
            'scout.track(kind="revenue", source="stripe", name="monthly_recurring_revenue", value=12000, unit="USD", verification_status="verified")'
        ),
        "environment": f"SCOUT_BASE_URL={base_url}\nSCOUT_API_KEY=scout_live_xxxxx",
    }
