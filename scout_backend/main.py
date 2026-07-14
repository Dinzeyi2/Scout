from fastapi import FastAPI

from scout_backend.api.routes import router
from scout_backend.models.database import init_db


def create_app() -> FastAPI:
    app = FastAPI(
        title="Scout Execution Intelligence API",
        version="0.1.0",
        description=(
            "Backend for issuing startup API keys, ingesting provenance-rich execution metadata, "
            "and translating software/physical-company raw facts into investor evidence."
        ),
    )

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    def health_payload() -> dict[str, str]:
        return {"status": "ok", "service": "scout-backend", "version": "0.1.0"}

    @app.get("/", tags=["system"])
    def root() -> dict[str, str]:
        return {
            **health_payload(),
            "docs": "/docs",
            "openapi": "/openapi.json",
            "api_prefix": "/v1",
        }

    @app.get("/health", tags=["system"])
    @app.get("/api/health", tags=["system"], include_in_schema=False)
    @app.get("/status", tags=["system"], include_in_schema=False)
    @app.get("/ping", tags=["system"], include_in_schema=False)
    def health() -> dict[str, str]:
        return health_payload()

    @app.get("/version", tags=["system"], include_in_schema=False)
    def version() -> dict[str, str]:
        return {"version": health_payload()["version"]}

    @app.get("/api", tags=["system"], include_in_schema=False)
    @app.get("/api/v1", tags=["system"], include_in_schema=False)
    def api_index() -> dict[str, str]:
        return {"api_prefix": "/v1", "docs": "/docs", "openapi": "/openapi.json"}

    app.include_router(router, prefix="/v1")
    return app


app = create_app()
