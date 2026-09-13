"""
error_handler.py — Global exception handling middleware for FastAPI.
Provides structured, user-friendly JSON error responses without leaking internal tracebacks.
"""
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("deepverify.error_handler")

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "message": exc.detail,
                "path": str(request.url.path),
            },
        )
    
    if isinstance(exc, RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": True,
                "status_code": 400,
                "message": "Invalid request payload or parameters",
                "details": exc.errors(),
                "path": str(request.url.path),
            },
        )
    
    logger.exception("Unhandled Exception at %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "status_code": 500,
            "message": "An internal server error occurred while processing your request.",
            "path": str(request.url.path),
        },
    )
