"""Connect merged v2 code without substituting rehearsal fixtures."""
from __future__ import annotations

import importlib
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse


def install(host: FastAPI) -> None:
    factory = os.environ.get("EXAMDATA_V2_FACTORY", "").strip()
    if factory:
        if ":" not in factory:
            raise ValueError("EXAMDATA_V2_FACTORY must be module:function returning ProductionAssembly")
        from .api.assembly import ProductionAssembly, create_production_app
        from .api.compose import attach_v2

        module, name = factory.split(":", 1)
        assembly = getattr(importlib.import_module(module), name)()
        if not isinstance(assembly, ProductionAssembly):
            raise TypeError("The v2 factory must return ProductionAssembly")
        attach_v2(host, application=create_production_app(assembly))
        host.state.integration_mode = "production"
        return

    host.state.integration_mode = "not_configured"

    @host.api_route("/api/v2/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def unavailable(path: str):
        return JSONResponse(status_code=503, content={
            "schema_version": "examdata.v2/1", "ok": False,
            "error": {"code": "production_sources_not_configured",
                      "message": "v2 code is installed; configure EXAMDATA_V2_FACTORY with real sources. Existing /api/v1 APIs remain available."},
            "data": None, "evidence": "unavailable", "fixture_fallback": False})
