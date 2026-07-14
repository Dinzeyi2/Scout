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

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router, prefix="/v1")
    return app


app = create_app()
