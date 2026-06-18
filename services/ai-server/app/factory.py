from __future__ import annotations

from fastapi import FastAPI

from .runtime_state import RuntimeContext, default_runtime_context
from .service_metadata import SERVICE_VERSION


def create_app(runtime_context: RuntimeContext | None = None) -> FastAPI:
    """Create the SmartFactory AI Server FastAPI application.

    Route registration is owned by the factory so contract/OpenAPI generation
    and `app.main:app` runtime startup use the same construction path without a
    generator-only bridge back into `app.main`. The mutable runtime state is an
    explicit injectable context; the default entrypoint uses the shared default
    context for backward-compatible single-process operation.
    """

    app = FastAPI(
        title="SmartFactory AI Server",
        version=SERVICE_VERSION,
        description="API-first MVP1 AI Server. Emits evidence only; WMS owns decisions.",
    )
    from .runtime_routes import register_routes

    register_routes(app, runtime_context=runtime_context or default_runtime_context)
    return app


__all__ = ["create_app"]
