from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from src.config import get_settings
from src.gatekeeper.admin_router import router as admin_router
from src.gatekeeper.router import router as gatekeeper_router


async def _api_key_middleware(request: Request, call_next):
    api_key = request.headers.get("X-API-Key")
    if api_key != get_settings().sentinel_api_key:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


def create_app() -> FastAPI:
    app = FastAPI(title="Sentinel Custody Engine", version="0.1.0")
    app.middleware("http")(_api_key_middleware)
    app.include_router(admin_router)
    app.include_router(gatekeeper_router)
    return app


app = create_app()
