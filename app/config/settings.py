from functools import lru_cache
from typing import List, Literal, Optional, Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


class ServiceSettings(BaseSettings):
    """Configuração completa da API, carregada do ambiente."""
    APP_NAME: str = Field(
        default="api-controla-ai",
        description="Identificador da aplicação, usado em logs e nas probes de saúde.",
        examples=["api-controla-ai"]
    )

    APP_ENV: Literal["development", "staging", "production"] = Field(
        default="production",
        description="Ambiente de execução. "
                    "Em 'production' a documentação interativa é desabilitada e os logs são emitidos em JSON.",
        examples=["production", "development"]
    )

    APP_DEBUG: bool = Field(
        default=False,
        description="Modo de depuração do FastAPI. Deve permanecer desligado fora do desenvolvimento.",
    )

    APP_PORT: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Porta TCP em que a aplicação escuta.",
        examples=[8000]
    )

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Nível mínimo de severidade registrado pelo structlog.",
        examples=["INFO", "DEBUG"],
    )

    TZ: str = Field(
        default="America/Sao_Paulo",
        description="Fuso horário do processo, no formato IANA.",
        examples=["America/Sao_Paulo"],
    )

    DATABASE_URL: SecretStr = Field(
        default=...,
        description="DSN de conexão do PostgreSQL no formato aceito pelo asyncpg.",
        examples=["postgres://usuario:senha@postgres:5432/controlaai"]
    )

    DATABASE_SCHEMA: str = Field(
        default="controla_ai",
        description="Schema aplicado ao search_path na inicialização de cada conexão do pool.",
        examples=["controla_ai"]
    )

    DATABASE_MIN_POOL_SIZE: int = Field(
        default=5,
        ge=1,
        description="Conexões mantidas abertas por processo, mesmo em ociosidade.",
        examples=[5]
    )

    DATABASE_MAX_POOL_SIZE: int = Field(
        default=15,
        ge=1,
        description="Teto de conexões por processo.",
        examples=[15]
    )

    DATABASE_COMMAND_TIMEOUT: int = Field(
        default=30,
        ge=1,
        description="Tempo limite, em segundos, para a execução de uma query.",
        examples=[30],
    )

    REDIS_URL: SecretStr = Field(
        default=...,
        description="URL de conexão do Redis.",
        examples=["redis://redis:6379/0"]
    )

    REDIS_CACHE_DB: int = Field(
        default=0,
        ge=0,
        le=15,
        description="Banco lógico do cache.",
        examples=[0]
    )

    REDIS_QUEUE_DB: int = Field(
        default=1,
        ge=0,
        le=15,
        description="Banco lógico das filas do arq.",
        examples=[1]
    )

    REDIS_METERING_DB: int = Field(
        default=2,
        ge=0,
        le=15,
        description="Banco lógico dos contadores de consumo.",
        examples=[2]
    )

    RECEIPT_STORAGE_ROOT: str = Field(
        default="/var/lib/controlaai/receipts",
        description="Diretório raiz dos comprovantes. "
                    "Os arquivos são gravados em {partner_id}/{user_id}/{receipt_id}.{ext} e referenciados por "
                    "RECEIPTS.FILE_PATH.",
        examples=["/var/lib/controlaai/receipts"]
    )

    RECEIPT_MAX_SIZE_BYTES: int = Field(
        default=10485760,
        ge=1,
        description="Tamanho máximo aceito no upload.",
        examples=[10485760]
    )

    RECEIPT_ALLOWED_MIME: Annotated[
        List[str],
        NoDecode,
        Field(
            default_factory=lambda: ["image/jpeg", "image/png", "application/pdf"],
            description="Tipos MIME aceitos no upload. "
                        "Aceita lista separada por vírgula na variável de ambiente.",
            examples=[["image/jpeg", "image/png", "application/pdf"]]
        )
    ]

    JWE_PRIVATE_KEY_PATH: str = Field(
        default="/run/secrets/jwe_private.pem",
        description="Caminho da chave privada RSA usada na decriptação dos tokens.",
        examples=["/run/secrets/jwe_private.pem"],
    )

    JWE_PUBLIC_KEY_PATH: str = Field(
        default="/run/secrets/jwe_public.pem",
        description="Caminho da chave pública RSA usada na emissão dos tokens.",
        examples=["/run/secrets/jwe_public.pem"]
    )

    JWE_ALGORITHM: str = Field(
        default="RSA-OAEP-256",
        description="Algoritmo de gerenciamento de chave do JWE, conforme RFC 7518.",
        examples=["RSA-OAEP-256"]
    )

    JWE_ENCRYPTION: str = Field(
        default="A256GCM",
        description="Algoritmo de criptografia do conteúdo do JWE, conforme RFC 7518.",
        examples=["A256GCM"]
    )

    JWE_ISSUER: str = Field(
        default="https://api.controla.ai",
        description="Emissor registrado na claim 'iss' do access token, conforme RFC 7519.",
        examples=["https://api.controla.ai"]
    )

    JWE_AUDIENCE: str = Field(
        default="controla-ai-api",
        description="Destinatário registrado na claim 'aud'. Rejeitar tokens de outra audiência impede que "
                    "um token emitido para outro serviço do mesmo domínio seja aceito aqui.",
        examples=["controla-ai-api"]
    )

    ACCESS_TOKEN_TTL_SECONDS: int = Field(
        default=900,
        ge=60,
        description="Validade do access token. Intervalo curto limita a janela de exploração em caso de vazamento.",
        examples=[900]
    )

    REFRESH_TOKEN_TTL_SECONDS: int = Field(
        default=2592000,
        ge=3600,
        description="Validade do refresh token, persistido em REFRESH_TOKENS.",
        examples=[2592000],
    )

    OCR_LANGUAGE: str = Field(
        default="por",
        description="Código do modelo de idioma do Tesseract, instalado na imagem de runtime.",
        examples=["por"]
    )

    OCR_CONFIDENCE_THRESHOLD: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Limiar da extração abaixo deste índice marca a transação para revisão manual.",
        examples=[0.85]
    )

    LLM_PROVIDER: str = Field(
        default="openai",
        description="Provedor do modelo de linguagem utilizado na inferência.",
        examples=["openai"]
    )

    LLM_BASE_URL: str = Field(
        default="https://api.openai.com/v1",
        description="Raiz da API do provedor. Isolada em configuração para permitir apontar "
                    "para um gateway compatível sem alterar o adaptador.",
        examples=["https://api.openai.com/v1"]
    )

    LLM_API_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Credencial de acesso ao provedor. Ausente, extração e assistente ficam indisponíveis.",
        examples=["sk-..."]
    )

    LLM_MODEL: str = Field(
        default="gpt-4.1-mini",
        description="Modelo usado na estruturação do comprovante. Deve suportar Structured Outputs "
                    "com `json_schema` e `strict`.",
        examples=["gpt-4.1-mini"]
    )

    LLM_TIMEOUT_SECONDS: int = Field(
        default=30,
        ge=1,
        description="Tempo limite das chamadas ao provedor.",
        examples=[30]
    )

    WEBHOOK_TIMEOUT_SECONDS: int = Field(
        default=10,
        ge=1,
        description="Tempo limite de cada tentativa de entrega do callback.",
        examples=[10]
    )

    WEBHOOK_MAX_ATTEMPTS: int = Field(
        default=3,
        ge=1,
        description="Tentativas de entrega do callback. Apenas falhas de rede e respostas 5xx são repetidas: "
                    "4xx indica contrato incompatível e repetir não muda o desfecho.",
        examples=[3]
    )

    WEBHOOK_RETRY_BACKOFF_SECONDS: float = Field(
        default=2.0,
        ge=0.0,
        description="Base do intervalo linear entre as tentativas de entrega.",
        examples=[2.0]
    )

    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="Modelo de geração dos vetores persistidos em VECTOR_EMBEDDINGS.",
        examples=["text-embedding-3-small"]
    )

    EMBEDDING_DIMENSIONS: int = Field(
        default=1536,
        ge=1,
        description="Dimensionalidade do vetor.",
        examples=[1536]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # noinspection PyNestedDecorators
    @field_validator("RECEIPT_ALLOWED_MIME", mode="before")
    @classmethod
    def _split_mime_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]

        return value

    @model_validator(mode="after")
    def _validate_pool_bounds(self) -> "ServiceSettings":
        if self.DATABASE_MAX_POOL_SIZE < self.DATABASE_MIN_POOL_SIZE:
            raise ValueError("DATABASE_MAX_POOL_SIZE não pode ser menor que DATABASE_MIN_POOL_SIZE")

        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache(maxsize=1)
def get_settings() -> ServiceSettings:
    return ServiceSettings()  # type: ignore
