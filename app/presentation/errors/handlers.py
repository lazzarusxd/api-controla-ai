from typing import Any, Dict, Tuple

from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError

from app.config.logging_setup import logger
from app.domain.types import OAuthErrorCode
from app.domain.exceptions.base import DomainError
from app.domain.exceptions.authentication_exceptions import AuthenticationError, InvalidClientError, InvalidTokenError
from app.domain.exceptions.transaction_exceptions import (
    TransactionError,
    UserNotFoundError,
    InvalidPeriodError,
    TransactionNotFoundError,
    TransactionNotEditableError
)


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

PROBLEM_TYPE_BASE = "https://controla.ai/problems"

_BUSINESS_RULE_PROBLEM: Tuple[int, str, str] = (
    status.HTTP_422_UNPROCESSABLE_ENTITY,
    "regra-de-negocio-violada",
    "Regra de negócio violada."
)

_TRANSACTION_PROBLEM: Dict[type, Tuple[int, str, str]] = {
    UserNotFoundError: (
        status.HTTP_404_NOT_FOUND,
        "usuario-nao-encontrado",
        "Usuário não encontrado."
    ),
    InvalidPeriodError: (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "periodo-invalido",
        "Período inválido."
    ),
    TransactionNotFoundError: (
        status.HTTP_404_NOT_FOUND,
        "lancamento-nao-encontrado",
        "Lançamento não encontrado."
    ),
    TransactionNotEditableError: (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "lancamento-imutavel",
        "Lançamento imutável."
    )
}


def _problem(
        title: str,
        detail: str,
        request: Request,
        status_code: int,
        problem_type: str,
        **extra: Any
) -> JSONResponse:
    """Monta um corpo application/problem+json conforme RFC 9457."""
    body: Dict[str, Any] = {
        "type": f"{PROBLEM_TYPE_BASE}/{problem_type}",
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

    @app.exception_handler(TransactionError)
    async def _transaction_error(request: Request, exc: TransactionError) -> JSONResponse:
        status_code, problem_type, title = _TRANSACTION_PROBLEM.get(type(exc), _BUSINESS_RULE_PROBLEM)

        return _problem(
            title=title,
            request=request,
            detail=exc.message,
            status_code=status_code,
            problem_type=problem_type
        )

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(
            request=request,
            detail=exc.message,
            title="Regra de negócio violada.",
            problem_type="regra-de-negocio-violada",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem(
            request=request,
            problem_type="payload-invalido",
            title="Corpo da requisição inválido.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A requisição não satisfaz o contrato do endpoint.",
            errors=[
                {"field": ".".join(str(part) for part in error.get("loc")), "message": error.get("msg")}
                for error in exc.errors()
            ]
        )

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", path=request.url.path, error=type(exc).__name__)

        return _problem(
            request=request,
            problem_type="erro-interno",
            title="Erro interno do servidor.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno no processamento da requisição."
        )
