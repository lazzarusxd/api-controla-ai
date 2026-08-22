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
    TransactionNotEditableError,
    TransactionNotUnderReviewError
)
from app.domain.exceptions.subscription_exceptions import (
    InvalidDueDayError,
    SubscriptionError,
    SubscriptionNotFoundError,
    SubscriptionOwnerNotFoundError
)
from app.domain.exceptions.assistant_exceptions import (
    AssistantError,
    EmptyQuestionError,
    AssistantUnavailableError
)
from app.domain.exceptions.receipt_exceptions import (
    ReceiptError,
    EmptyReceiptError,
    ReceiptNotFoundError,
    ReceiptTooLargeError,
    ReceiptExtractionError,
    WebhookNotRegisteredError,
    UnsupportedReceiptTypeError
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

_TRANSACTION_PROBLEM: Dict[type, Tuple[int, str]] = {
    UserNotFoundError: (status.HTTP_404_NOT_FOUND, "Usuário não encontrado."),
    InvalidPeriodError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Período inválido."),
    TransactionNotFoundError: (status.HTTP_404_NOT_FOUND, "Lançamento não encontrado."),
    TransactionNotEditableError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Lançamento imutável."),
    TransactionNotUnderReviewError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Lançamento não pendente de revisão.")
}

_RECEIPT_PROBLEM: Dict[type, Tuple[int, str]] = {
    EmptyReceiptError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Arquivo vazio."),
    ReceiptNotFoundError: (status.HTTP_404_NOT_FOUND, "Comprovante não encontrado."),
    WebhookNotRegisteredError: (status.HTTP_404_NOT_FOUND, "Webhook não registrado."),
    ReceiptTooLargeError: (status.HTTP_413_CONTENT_TOO_LARGE, "Arquivo grande demais."),
    ReceiptExtractionError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Extração do comprovante inviável."),
    UnsupportedReceiptTypeError: (status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Tipo de arquivo não suportado.")
}

_SUBSCRIPTION_PROBLEM: Dict[type, Tuple[int, str]] = {
    InvalidDueDayError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Dia de vencimento inválido."),
    SubscriptionNotFoundError: (status.HTTP_404_NOT_FOUND, "Recorrência não encontrada."),
    SubscriptionOwnerNotFoundError: (status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
}

_ASSISTANT_PROBLEM: Dict[type, Tuple[int, str]] = {
    EmptyQuestionError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Pergunta vazia."),
    AssistantUnavailableError: (status.HTTP_503_SERVICE_UNAVAILABLE, "Assistente indisponível.")
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

    @app.exception_handler(TransactionError)
    async def _transaction_error(request: Request, exc: TransactionError) -> JSONResponse:
        status_code, title = _TRANSACTION_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(ReceiptError)
    async def _receipt_error(request: Request, exc: ReceiptError) -> JSONResponse:
        status_code, title = _RECEIPT_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(SubscriptionError)
    async def _subscription_error(request: Request, exc: SubscriptionError) -> JSONResponse:
        status_code, title = _SUBSCRIPTION_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(AssistantError)
    async def _assistant_error(request: Request, exc: AssistantError) -> JSONResponse:
        status_code, title = _ASSISTANT_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(
            request=request,
            detail=exc.message,
            title="Regra de negócio violada.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem(
            request=request,
            title="Corpo da requisição inválido.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
            title="Erro interno do servidor.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno no processamento da requisição."
        )
