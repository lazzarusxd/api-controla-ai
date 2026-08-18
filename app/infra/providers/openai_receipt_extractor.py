import json
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Final

import httpx

from app.config.logging_setup import logger
from app.application.interfaces import IReceiptExtractor
from app.domain.types import TransactionStatus, TransactionType
from app.application.dto import ExtractedTransactionDTO, OcrExtractionDTO
from app.domain.exceptions.receipt_exceptions import ReceiptExtractionError


_SYSTEM_PROMPT: Final[str] = (
    "Você estrutura comprovantes financeiros brasileiros a partir de texto extraído por OCR. "
    "Considere apenas o que está no texto: nunca invente valor, data ou estabelecimento. "
    "Valores estão em Real, com vírgula como separador decimal, e datas no formato dd/mm/aaaa. "
    "Comprovante de pagamento, cupom fiscal e recibo são EXPENSE; comprovante de recebimento, "
    "depósito e transferência recebida são INCOME. Use SETTLED quando o texto indicar pagamento já "
    "efetuado e PENDING quando indicar boleto ou fatura a vencer, informando due_date nesse caso. "
    "A categoria deve pertencer a um plano de contas doméstico usual: Alimentação, Transporte, "
    "Moradia, Saúde, Educação, Lazer, Serviços, Vestuário, Salário, Investimentos ou Outros. "
    "O campo confidence expressa sua certeza sobre a extração como um todo, de 0 a 1: reduza-o "
    "quando o valor, a data ou o estabelecimento estiverem ilegíveis ou ambíguos no texto."
)

_RESPONSE_SCHEMA: Final[Dict[str, Any]] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "type",
        "amount",
        "category",
        "description",
        "transaction_date",
        "status",
        "due_date",
        "confidence"
    ],
    "properties": {
        "type": {
            "type": "string",
            "enum": ["INCOME", "EXPENSE"],
            "description": "Natureza do lançamento."
        },
        "amount": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": "Valor absoluto do comprovante, em Real."
        },
        "category": {
            "type": "string",
            "description": "Categoria do plano de contas."
        },
        "description": {
            "type": "string",
            "description": "Descrição curta, com o estabelecimento quando identificável."
        },
        "transaction_date": {
            "type": "string",
            "description": "Data do fato gerador, no formato aaaa-mm-dd."
        },
        "status": {
            "type": "string",
            "enum": ["SETTLED", "PENDING"],
            "description": "SETTLED para pagamento efetuado, PENDING para documento a vencer."
        },
        "due_date": {
            "type": ["string", "null"],
            "description": "Vencimento no formato aaaa-mm-dd. Nulo quando o documento já está liquidado."
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Certeza do modelo sobre a extração, de 0 a 1."
        }
    }
}


class OpenAiReceiptExtractor(IReceiptExtractor):

    def __init__(self, api_key: str, model: str, base_url: str, timeout_seconds: int) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def extract_transaction(self, ocr_extraction: OcrExtractionDTO) -> ExtractedTransactionDTO:
        payload: Dict[str, Any] = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": ocr_extraction.raw_text}
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "strict": True,
                    "name": "extracted_transaction",
                    "schema": _RESPONSE_SCHEMA
                }
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    url=f"{self._base_url}/chat/completions",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}"
                    }
                )

                response.raise_for_status()

                body = response.json()

        except httpx.HTTPError as exc:
            logger.warning("llm_request_failed", error=type(exc).__name__)

            raise ReceiptExtractionError("Provedor de linguagem indisponível para estruturar o comprovante.") from exc

        return self._to_dto(body=body)

    @staticmethod
    def _to_dto(body: Dict[str, Any]) -> ExtractedTransactionDTO:
        try:
            choices = body.get("choices") or []
            content = choices[0].get("message").get("content")
            extracted: Dict[str, Any] = json.loads(content)

            due_date = extracted.get("due_date")
            status = TransactionStatus(extracted.get("status"))

            return ExtractedTransactionDTO(
                status=status,
                category=extracted.get("category"),
                description=extracted.get("description"),
                type=TransactionType(extracted.get("type")),
                amount=Decimal(str(extracted.get("amount"))),
                confidence=Decimal(str(extracted.get("confidence"))),
                due_date=date.fromisoformat(due_date) if due_date else None,
                transaction_date=date.fromisoformat(extracted.get("transaction_date"))
            )

        except (AttributeError, IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("llm_response_unusable", error=type(exc).__name__)

            raise ReceiptExtractionError("Resposta do provedor fora do contrato esperado.") from exc
