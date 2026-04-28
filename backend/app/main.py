from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, get_settings
from app.database import create_db_and_tables, engine
from app.responses import ApiError, api_error_handler, api_error_response
from app.responses import api_success
from app.routers import admin, user
from app.seed import seed_database
from sqlmodel import Session


class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


app = FastAPI(
    title="Virtual Character Life System Backend",
    version=get_settings().app_version,
    description="FastAPI + SQLite + SQLModel backend with mock and external LLM/ComfyUI modes.",
    default_response_class=UTF8JSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        seed_database(session)


@app.exception_handler(ApiError)
async def handle_api_error(request, exc: ApiError):
    return await api_error_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_, exc: RequestValidationError):
    return api_error_response("VALIDATION_FAILED", "Request validation failed", 422, exc.errors())


@app.exception_handler(HTTPException)
async def handle_http_error(_, exc: HTTPException):
    return api_error_response("HTTP_ERROR", str(exc.detail), exc.status_code)


app.include_router(user.router)
app.include_router(admin.router)
(BASE_DIR / "data" / "generated").mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=str(BASE_DIR / "data" / "generated")), name="generated")


@app.get("/health")
async def health_check():
    return api_success({"status": "ok"})


@app.get("/api/system/version")
async def version_check():
    settings = get_settings()
    return api_success(
        {
            "version": settings.app_version,
            "llmEnabled": settings.llm_enabled,
            "comfyuiEnabled": settings.comfyui_enabled,
        }
    )
