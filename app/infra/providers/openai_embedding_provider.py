from typing import Any, Dict, List

import httpx

from app.config.logging_setup import logger
from app.application.interfaces import IEmbeddingProvider
from app.domain.exceptions.assistant_exceptions import AssistantUnavailableError


class OpenAiEmbeddingProvider(IEmbeddingProvider):

    def __init__(self, api_key: str, model: str, base_url: str, dimensions: int, timeout_seconds: int) -> None:
        self._model = model
        self._api_key = api_key
        self._dimensions = dimensions
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        payload: Dict[str, Any] = {
            "input": texts,
            "model": self._model,
            "dimensions": self._dimensions
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    url=f"{self._base_url}/embeddings",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}"
                    }
                )

                response.raise_for_status()

                body = response.json()

        except httpx.HTTPError as exc:
            logger.warning("embedding_request_failed", error=type(exc).__name__)

            raise AssistantUnavailableError("Provedor de embeddings indisponível.") from exc

        return self._to_vectors(body=body)

    @staticmethod
    def _to_vectors(body: Dict[str, Any]) -> List[List[float]]:
        try:
            items = sorted(body.get("data") or [], key=lambda item: int(item.get("index")))

            return [[float(value) for value in item.get("embedding")] for item in items]

        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("embedding_response_unusable", error=type(exc).__name__)

            raise AssistantUnavailableError("Resposta do provedor de embeddings fora do contrato.") from exc
