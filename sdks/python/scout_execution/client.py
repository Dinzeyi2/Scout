from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

SignalKind = Literal[
    "engineering",
    "infrastructure",
    "product",
    "customer",
    "operations",
    "manufacturing",
    "compliance",
    "revenue",
]
VerificationStatus = Literal["verified", "attested", "self_reported", "inferred", "unverified"]
StartupType = Literal["software", "physical", "hybrid"]


class ScoutApiError(RuntimeError):
    def __init__(self, message: str, status_code: int, details: Any):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


@dataclass(frozen=True)
class Signal:
    kind: SignalKind
    source: str
    name: str
    value: float
    unit: str = "count"
    verification_status: VerificationStatus = "self_reported"
    source_event_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    occurred_at: str | None = None
    observed_at: str | None = None


class Scout:
    def __init__(self, api_key: str, base_url: str = "https://your-scout-api.up.railway.app"):
        if not api_key:
            raise ValueError("Scout api_key is required. Store it in a server-side environment variable.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=15.0)

    @classmethod
    def from_env(cls) -> Scout:
        return cls(
            api_key=os.environ.get("SCOUT_API_KEY", ""),
            base_url=os.environ.get("SCOUT_BASE_URL", "https://your-scout-api.up.railway.app"),
        )

    @classmethod
    def monitor(
        cls,
        service_name: str | None = None,
        environment: str | None = None,
        heartbeat_interval_seconds: int = 60,
        capture_errors: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> Scout:
        scout = cls.from_env()
        scout.start_monitoring(
            service_name=service_name,
            environment=environment,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
            capture_errors=capture_errors,
            metadata=metadata,
        )
        return scout

    def start_monitoring(
        self,
        service_name: str | None = None,
        environment: str | None = None,
        heartbeat_interval_seconds: int = 60,
        capture_errors: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        base_metadata = {
            "service_name": service_name or os.environ.get("SERVICE_NAME") or os.environ.get("RAILWAY_SERVICE_NAME") or "app",
            "environment": environment or os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("ENVIRONMENT") or "unknown",
            "railway_service_id": os.environ.get("RAILWAY_SERVICE_ID"),
            "railway_environment_id": os.environ.get("RAILWAY_ENVIRONMENT_ID"),
            **(metadata or {}),
        }
        self._safe_track(
            kind="infrastructure",
            source="scout_sdk",
            name="application_started",
            value=1,
            unit="event",
            verification_status="attested",
            source_event_id=f"scout-sdk-start-{int(time.time() * 1000)}",
            metadata=base_metadata,
        )

        if heartbeat_interval_seconds > 0:
            thread = threading.Thread(
                target=self._heartbeat_loop,
                args=(heartbeat_interval_seconds, base_metadata),
                daemon=True,
            )
            thread.start()

        if capture_errors:
            previous_excepthook = sys.excepthook

            def scout_excepthook(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
                self.capture_error(exc, {**base_metadata, "error_type": exc_type.__name__, "traceback": "".join(traceback.format_tb(tb))})
                previous_excepthook(exc_type, exc, tb)

            sys.excepthook = scout_excepthook

    def _heartbeat_loop(self, heartbeat_interval_seconds: int, metadata: dict[str, Any]) -> None:
        while True:
            time.sleep(heartbeat_interval_seconds)
            self._safe_track(
                kind="infrastructure",
                source="scout_sdk",
                name="application_heartbeat",
                value=1,
                unit="heartbeat",
                verification_status="attested",
                source_event_id=f"scout-sdk-heartbeat-{int(time.time() * 1000)}",
                metadata=metadata,
            )

    def capture_error(self, error: BaseException, metadata: dict[str, Any] | None = None) -> Any:
        return self.track(
            kind="infrastructure",
            source="scout_sdk",
            name="application_error",
            value=1,
            unit="error",
            verification_status="attested",
            source_event_id=f"scout-sdk-error-{int(time.time() * 1000)}",
            metadata={"message": str(error), "error_class": error.__class__.__name__, **(metadata or {})},
        )

    def _safe_track(self, **kwargs: Any) -> None:
        try:
            self.track(**kwargs)
        except Exception:
            return


    def asgi_middleware(self, app: Any, metadata: dict[str, Any] | None = None) -> Any:
        scout = self
        base_metadata = metadata or {}

        async def middleware(scope: dict[str, Any], receive: Any, send: Any) -> None:
            if scope.get("type") != "http":
                await app(scope, receive, send)
                return

            started_at = time.time()
            status_code: int | None = None

            async def send_wrapper(message: dict[str, Any]) -> None:
                nonlocal status_code
                if message.get("type") == "http.response.start":
                    status_code = message.get("status")
                await send(message)

            try:
                await app(scope, receive, send_wrapper)
            except Exception as exc:
                self.capture_error(exc, {**base_metadata, "path": scope.get("path"), "method": scope.get("method")})
                raise
            finally:
                duration_ms = round((time.time() - started_at) * 1000, 2)
                scout._safe_track(
                    kind="infrastructure",
                    source="scout_sdk",
                    name="http_request",
                    value=duration_ms,
                    unit="ms",
                    verification_status="attested",
                    source_event_id=f"scout-sdk-http-{int(time.time() * 1000)}",
                    metadata={
                        "method": scope.get("method"),
                        "path": scope.get("path"),
                        "status_code": status_code,
                        "success": (status_code or 500) < 500,
                        **base_metadata,
                    },
                )

        return middleware

    def instrument_fastapi(self, app: Any, metadata: dict[str, Any] | None = None) -> None:
        scout = self
        base_metadata = metadata or {}

        @app.middleware("http")
        async def scout_middleware(request: Any, call_next: Any) -> Any:
            started_at = time.time()
            try:
                response = await call_next(request)
            except Exception as exc:
                scout.capture_error(
                    exc,
                    {
                        **base_metadata,
                        "path": str(request.url.path),
                        "method": request.method,
                    },
                )
                raise
            duration_ms = round((time.time() - started_at) * 1000, 2)
            scout._safe_track(
                kind="infrastructure",
                source="scout_sdk",
                name="http_request",
                value=duration_ms,
                unit="ms",
                verification_status="attested",
                source_event_id=f"scout-sdk-http-{int(time.time() * 1000)}",
                metadata={
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "success": response.status_code < 500,
                    **base_metadata,
                },
            )
            return response

    def monitor_function(self, name: str, fn: Any, metadata: dict[str, Any] | None = None) -> Any:
        started_at = time.time()
        try:
            result = fn()
        except Exception as exc:
            self.capture_error(exc, {"function_name": name, **(metadata or {})})
            raise
        self._safe_track(
            kind="operations",
            source="scout_sdk",
            name="function_completed",
            value=round((time.time() - started_at) * 1000, 2),
            unit="ms",
            verification_status="attested",
            source_event_id=f"scout-sdk-function-{name}-{int(time.time() * 1000)}",
            metadata={"function_name": name, "success": True, **(metadata or {})},
        )
        return result

    def track(self, *, kind: SignalKind, source: str, name: str, value: float, unit: str = "count", verification_status: VerificationStatus = "self_reported", source_event_id: str | None = None, metadata: dict[str, Any] | None = None, occurred_at: str | None = None, observed_at: str | None = None) -> Any:
        return self._request(
            "POST",
            "/v1/signals",
            json={
                "kind": kind,
                "source": source,
                "name": name,
                "value": value,
                "unit": unit,
                "verification_status": verification_status,
                "source_event_id": source_event_id,
                "metadata": metadata or {},
                "occurred_at": occurred_at,
                "observed_at": observed_at,
            },
        )

    def track_signal(self, signal: Signal) -> Any:
        return self.track(**signal.__dict__)

    def connect_github_repository(self, owner: str, repo: str, branch: str = "main") -> Any:
        return self._request("POST", "/v1/connectors/github/public-repository", json={"owner": owner, "repo": repo, "branch": branch})

    def founder_dashboard(self) -> Any:
        return self._request("GET", "/v1/founder-dashboard")

    def investor_dashboard(self) -> Any:
        return self._request("GET", "/v1/investor-dashboard")

    def investor_report(self) -> Any:
        return self._request("GET", "/v1/investor-report")

    def execution_narrative(self) -> Any:
        return self._request("GET", "/v1/execution-narrative")

    def evidence_timeline(self) -> Any:
        return self._request("GET", "/v1/evidence-timeline")

    def audit_logs(self) -> Any:
        return self._request("GET", "/v1/security/audit-logs")

    def data_inventory(self) -> Any:
        return self._request("GET", "/v1/security/data-inventory")

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.client.request(method, f"{self.base_url}{path}", **kwargs)
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        if response.status_code >= 400:
            raise ScoutApiError(f"Scout API request failed with {response.status_code}", response.status_code, payload)
        return payload


def create_startup(base_url: str, name: str, type: StartupType = "software", website: str | None = None, api_key_name: str = "default") -> Any:
    response = httpx.post(
        f"{base_url.rstrip('/')}/v1/startups",
        json={"name": name, "type": type, "website": website, "api_key_name": api_key_name},
        timeout=15.0,
    )
    payload = response.json()
    if response.status_code >= 400:
        raise ScoutApiError(f"Scout startup creation failed with {response.status_code}", response.status_code, payload)
    return payload
