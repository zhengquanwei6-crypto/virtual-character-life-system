from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: Any = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def request_id() -> str:
    return f"req_{uuid4().hex}"


def _snake_to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


PRESERVE_VALUE_KEYS = {
    "workflow_json",
    "workflowJson",
    "mappings",
    "parameter_snapshot",
    "parameterSnapshot",
}


def camelize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    encoded = jsonable_encoder(value)
    if isinstance(encoded, list):
        return [camelize(item) for item in encoded]
    if isinstance(encoded, dict):
        return {
            _snake_to_camel(key): jsonable_encoder(item) if key in PRESERVE_VALUE_KEYS else camelize(item)
            for key, item in encoded.items()
        }
    return encoded


def api_success(data: Any = None) -> dict[str, Any]:
    return {
        "success": True,
        "data": camelize(data),
        "error": None,
        "requestId": request_id(),
    }


def api_error_response(code: str, message: str, status_code: int = 400, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        media_type="application/json; charset=utf-8",
        content=jsonable_encoder(
            {
                "success": False,
                "data": None,
                "error": {
                    "code": code,
                    "message": message,
                    "details": camelize(details),
                },
                "requestId": request_id(),
            }
        ),
    )


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return api_error_response(exc.code, exc.message, exc.status_code, exc.details)
