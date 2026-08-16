import base64
import binascii
from typing import Annotated, Optional, Tuple

from fastapi import APIRouter, Depends, Form, Request, Response, status

from app.config.logging_setup import logger
from app.domain.types import GrantType, TokenType
from app.application.usecases.authentication.refresh_session import RefreshSessionUseCase
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse, TokenResponse
from app.application.usecases.authentication.authenticate_client import AuthenticateClientUseCase
from app.domain.exceptions.authentication_exceptions import InvalidClientError, UnsupportedGrantTypeError
from app.presentation.api.v1.authentication.dependencies import get_authenticate_use_case, get_refresh_use_case
from app.application.dto.authentication import ClientCredentialsRequestDTO, RefreshSessionRequestDTO, TokenPairDTO


router = APIRouter(prefix="/oauth", tags=["Autenticação"])


def _extract_basic_credentials(request: Request) -> Optional[Tuple[str, str]]:
    header = request.headers.get("Authorization")

    if not header:
        return None

    scheme, _, encoded = header.partition(" ")

    if scheme.lower() != "basic" or not encoded:
        return None

    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None

    client_id, separator, client_secret = decoded.partition(":")

    if not separator:
        return None

    return client_id, client_secret


@router.post(
    path="/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Emite ou renova a sessão do parceiro.",
    description="Endpoint único de emissão e renovação, conforme a RFC 6749. O fluxo é determinado pelo "
                "parâmetro `grant_type`.\n\n"
                "- **client_credentials**: autenticação inicial. As credenciais podem ser apresentadas via HTTP "
                "Basic (preferencial) ou nos parâmetros `client_id` e `client_secret` do corpo.\n"
                "- **refresh_token**: renovação sem reapresentar o secret. O token anterior é invalidado no ato; "
                "reapresentá-lo é tratado como indício de vazamento e encerra todas as sessões ativas do cliente.\n\n"
                "O corpo é codificado como `application/x-www-form-urlencoded`, conforme exigido pela seção 4.4.2.",
    responses={
        200: {
            "model": TokenResponse,
            "description": "Sessão estabelecida ou renovada."
        },
        400: {
            "model": OAuthErrorResponse,
            "description": "`invalid_grant` para refresh token inválido, expirado ou já consumido; "
                           "`unsupported_grant_type` para grant_type fora do conjunto suportado."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "`invalid_client`: credencial inexistente, secret incorreto, credencial revogada ou "
                           "parceiro inativo. As quatro condições são indistinguíveis por decisão de segurança."
        }
    }
)
async def issue_token(
        request: Request,
        response: Response,
        refresh_use_case: Annotated[RefreshSessionUseCase, Depends(get_refresh_use_case)],
        authenticate_use_case: Annotated[AuthenticateClientUseCase, Depends(get_authenticate_use_case)],
        grant_type: Annotated[str, Form(description="Fluxo de concessão: client_credentials ou refresh_token.")],
        client_secret: Annotated[Optional[str], Form(description="Segredo do cliente.")] = None,
        refresh_token: Annotated[Optional[str], Form(description="Refresh token vigente.")] = None,
        client_id: Annotated[Optional[str], Form(description="Identificador público do cliente.")] = None
) -> TokenResponse:
    response.headers["Pragma"] = "no-cache"
    response.headers["Cache-Control"] = "no-store"

    if grant_type == GrantType.CLIENT_CREDENTIALS:
        basic = _extract_basic_credentials(request)

        if basic is not None:
            client_id, client_secret = basic

        if not client_id or not client_secret:
            logger.info("token_request_rejected", reason="missing_credentials")
            raise InvalidClientError("Credenciais do cliente não informadas.")

        pair: TokenPairDTO = await authenticate_use_case.execute(
            ClientCredentialsRequestDTO(
                client_id=client_id,
                client_secret=client_secret
            )
        )

    elif grant_type == GrantType.REFRESH_TOKEN:
        if not refresh_token:
            logger.info("token_request_rejected", reason="missing_refresh_token")
            raise InvalidClientError("Refresh token não informado.")

        pair = await refresh_use_case.execute(
            RefreshSessionRequestDTO(refresh_token=refresh_token)
        )

    else:
        logger.info("token_request_rejected", reason="unsupported_grant_type", grant_type=grant_type)
        raise UnsupportedGrantTypeError(grant_type)

    return TokenResponse(
        expires_in=pair.expires_in,
        token_type=TokenType.BEARER,
        access_token=pair.access_token,
        refresh_token=pair.refresh_token
    )
