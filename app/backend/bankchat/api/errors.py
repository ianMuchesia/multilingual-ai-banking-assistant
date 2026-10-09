"""Map errors to HTTP responses shaped {"detail": "<message>"}: service errors -> 400 / 404 / 409,
request validation errors -> 400 (the contract uses 400 for bad input, not FastAPI's 422)."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from bankchat.services.errors import ConflictError, InvalidInputError, NotFoundError, ServiceError

STATUS_BY_ERROR: dict[type[ServiceError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    InvalidInputError: status.HTTP_400_BAD_REQUEST,
}


async def _service_error_handler(request: Request, exc: Exception) -> JSONResponse:
    code = next((c for cls, c in STATUS_BY_ERROR.items() if isinstance(exc, cls)), status.HTTP_400_BAD_REQUEST)
    return JSONResponse(status_code=code, content={"detail": str(exc)})


def _describe(error: dict) -> str:
    location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
    return f"{location}: {error.get('msg', 'invalid value')}" if location else str(error.get("msg", "invalid value"))


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    errors = exc.errors() if isinstance(exc, RequestValidationError) else []
    detail = "; ".join(_describe(e) for e in errors) or "invalid request"
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": detail})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ServiceError, _service_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
