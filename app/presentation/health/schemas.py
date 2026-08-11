from typing import Dict, Literal

from pydantic import BaseModel, Field


DependencyStatus = Literal["up", "down"]


class LivenessResponse(BaseModel):
    """Resposta de /health/liveness."""
    status: Literal["alive"] = Field(
        default="alive",
        description="Confirmação de que o processo responde, sem refletir o estado das dependências.",
        examples=["alive"]
    )
    app: str = Field(
        default=...,
        description="Identificador da aplicação que atendeu à requisição.",
        examples=["api-controla-ai"]
    )


class StartupResponse(BaseModel):
    """Resposta de /health/startup."""
    status: Literal["started", "starting"] = Field(
        default=...,
        description="Indica se o lifespan concluiu a abertura dos recursos; 'starting' responde com 503.",
        examples=["started", "starting"]
    )
    dependencies: Dict[str, DependencyStatus] = Field(
        default=...,
        description="Estado de inicialização de cada dependência, sem execução de comando remoto.",
        examples=[{"postgres": "up", "redis": "up"}]
    )


class ReadinessResponse(BaseModel):
    """Resposta de /health/readiness."""
    status: Literal["ready", "not_ready"] = Field(
        default=...,
        description="Indica se a instância pode receber tráfego; 'not_ready' responde com 503.",
        examples=["ready", "not_ready"]
    )
    dependencies: Dict[str, DependencyStatus] = Field(
        default=...,
        description="Resultado da verificação ativa de cada dependência, executada a cada chamada.",
        examples=[{"postgres": "up", "redis": "down"}]
    )
