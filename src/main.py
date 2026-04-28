from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from src.config import get_settings
from src.gatekeeper.admin_router import router as admin_router
from src.gatekeeper.router import router as gatekeeper_router

_ROOT = Path(__file__).resolve().parent.parent


async def _api_key_middleware(request: Request, call_next):
    # Dashboard and its static assets served without auth
    if request.url.path in ("/dashboard", "/dashboard.html"):
        return await call_next(request)
    api_key = request.headers.get("X-API-Key")
    if api_key != get_settings().sentinel_api_key:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


def create_app() -> FastAPI:
    app = FastAPI(title="Sentinel Custody Engine", version="0.1.0")
    app.middleware("http")(_api_key_middleware)
    app.include_router(admin_router)
    app.include_router(gatekeeper_router)

    @app.get("/dashboard", include_in_schema=False)
    async def dashboard():
        return FileResponse(_ROOT / "dashboard.html")

    return app


app = create_app()
