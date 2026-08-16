from enum import StrEnum


class GrantType(StrEnum):
    """Fluxos de concessão suportados (RFC 6749, seções 4.4 e 6)."""

    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"  # noqa: S105 — identificador de fluxo, não segredo


class TokenType(StrEnum):
    """Esquema de apresentação do access token (RFC 6750)."""

    BEARER = "Bearer"


class OAuthErrorCode(StrEnum):
    """Códigos de erro do endpoint de token (RFC 6749, seção 5.2).

    A RFC 6750, seção 3.1, acrescenta INVALID_TOKEN para o consumo de rotas
    protegidas, fora do escopo da emissão.
    """

    INVALID_REQUEST = "invalid_request"
    INVALID_CLIENT = "invalid_client"
    INVALID_GRANT = "invalid_grant"
    UNAUTHORIZED_CLIENT = "unauthorized_client"
    UNSUPPORTED_GRANT_TYPE = "unsupported_grant_type"
    INVALID_SCOPE = "invalid_scope"
    INVALID_TOKEN = "invalid_token"  # noqa: S105 — código de erro, não segredo
