from typing import List

from app.config.logging_setup import logger
from app.domain.entities import Transaction
from app.domain.types import EmbeddingSourceType, TransactionType
from app.application.interfaces import IEmbeddingProvider, IEmbeddingRepository
from app.application.dto import EmbeddingRecordDTO, IndexUserContextRequestDTO, IndexingResultDTO


class ContextIndexingService:

    def __init__(
            self,
            embedding_provider: IEmbeddingProvider,
            embedding_repository: IEmbeddingRepository
    ) -> None:
        self._embedding_provider = embedding_provider
        self._embedding_repository = embedding_repository

    async def index(self, index_user_context_request: IndexUserContextRequestDTO) -> IndexingResultDTO:
        transactions = await self._embedding_repository.list_stale_transactions(
            user_id=index_user_context_request.user_id,
            partner_id=index_user_context_request.partner_id,
            batch_size=index_user_context_request.batch_size
        )

        if not transactions:
            return IndexingResultDTO(partner_id=index_user_context_request.partner_id)

        texts = [self._to_context_text(transaction=transaction) for transaction in transactions]

        vectors = await self._embedding_provider.embed(texts=texts)

        records = self._to_records(transactions=transactions, texts=texts, vectors=vectors)

        indexed = await self._embedding_repository.upsert_many(
            records=records,
            partner_id=index_user_context_request.partner_id
        )

        logger.info(
            "assistant_context_indexed",
            indexed=indexed,
            candidates=len(transactions),
            partner_id=str(index_user_context_request.partner_id),
            user_id=str(index_user_context_request.user_id) if index_user_context_request.user_id else None
        )

        return IndexingResultDTO(
            indexed=indexed,
            skipped=len(transactions) - indexed,
            partner_id=index_user_context_request.partner_id
        )

    @staticmethod
    def _to_records(
            texts: List[str],
            vectors: List[List[float]],
            transactions: List[Transaction]
    ) -> List[EmbeddingRecordDTO]:
        records: List[EmbeddingRecordDTO] = []

        for transaction, text, vector in zip(transactions, texts, vectors):
            records.append(
                EmbeddingRecordDTO(
                    vector=vector,
                    context_text=text,
                    user_id=transaction.user_id,
                    partner_id=transaction.partner_id,
                    source_id=transaction.transaction_id,
                    source_type=EmbeddingSourceType.TRANSACTION
                )
            )

        return records

    @staticmethod
    def _to_context_text(transaction: Transaction) -> str:
        """Narrativa em português: o texto indexado é o mesmo que o modelo vai ler."""
        nature = "Receita" if transaction.type is TransactionType.INCOME else "Despesa"

        amount = f"R$ {transaction.amount:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")

        parts: List[str] = [
            f"{nature} de {amount} em {transaction.transaction_date.strftime('%d/%m/%Y')}",
            f"categoria {transaction.category}",
            f"descrição {transaction.description}",
            f"situação {transaction.status.value}"
        ]

        if transaction.due_date is not None:
            parts.append(f"vencimento em {transaction.due_date.strftime('%d/%m/%Y')}")

        if transaction.receipt_id is not None:
            parts.append("originada de comprovante processado por OCR")

        return ". ".join(parts) + "."
