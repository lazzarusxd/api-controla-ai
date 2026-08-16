from typing import Any, Dict

from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError

from app.config.logging_setup import logger
from app.domain.types import OAuthErrorCode
from app.domain.exceptions.base import DomainError
from app.domain.exceptions.authentication_exceptions import AuthenticationError, InvalidClientError, InvalidTokenError


PROBLEM_JSON = "application/problem+json"

_OAUTH_STATUS: Dict[OAuthErrorCode, int] = {
    OAuthErrorCode.INVALID_SCOPE: status.HTTP_400_BAD_REQUEST,
    OAuthErrorCode.INVALID_GRANT: status.HTTP_400_BAD_REQUEST,
    OAuthErrorCode.INVALID_TOKEN: status.HTTP_401_UNAUTHORIZED,
    OAuthErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    OAuthErrorCode.INVALID_CLIENT: status.HTTP_401_UNAUTHORIZED,
    OAuthErrorCode.UNAUTHORIZED_CLIENT: status.HTTP_401_UNAUTHORIZED,
    OAuthErrorCode.UNSUPPORTED_GRANT_TYPE: status.HTTP_400_BAD_REQUEST
}


def _problem(request: Request, status_code: int, title: str, detail: str, **extra: Any) -> JSONResponse:
    """Monta um corpo application/problem+json conforme RFC 9457."""
    body: Dict[str, Any] = {
        "type": f"https://controla.ai/problems/{title}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": str(request.url.path),
        **extra
    }

    return JSONResponse(status_code=status_code, content=body, media_type=PROBLEM_JSON)


def register_exception_handlers(app: FastAPI) -> None:
    """Registra a tradução de exceções em respostas HTTP."""
    @app.exception_handler(AuthenticationError)
    async def _authentication_error(_request: Request, exc: AuthenticationError) -> JSONResponse:
        status_code = _OAUTH_STATUS.get(exc.oauth_error, status.HTTP_400_BAD_REQUEST)
        headers: Dict[str, str] = {"Cache-Control": "no-store", "Pragma": "no-cache"}

        if isinstance(exc, InvalidClientError):
            headers["WWW-Authenticate"] = 'Basic realm="controla-ai"'

        if isinstance(exc, InvalidTokenError):
            headers["WWW-Authenticate"] = (
                f'Bearer realm="controla-ai", error="{exc.oauth_error.value}", '
                f'error_description="{exc.message}"'
            )

        return JSONResponse(
            headers=headers,
            status_code=status_code,
            content={"error": exc.oauth_error.value, "error_description": exc.message}
        )

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(
            request=request,
            detail=exc.message,
            title="regra-de-negocio-violada",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem(
            request=request,
            title="payload-invalido",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A requisição não satisfaz o contrato do endpoint.",
            errors=[
                {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
                for error in exc.errors()
            ]
        )

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", path=request.url.path, error=type(exc).__name__)

        return _problem(
            request=request,
            title="erro-interno",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno no processamento da requisição."
        )
