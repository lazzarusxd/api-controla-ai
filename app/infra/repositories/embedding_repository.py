from uuid import UUID
from decimal import Decimal
from typing import Any, List, Optional, Tuple

import asyncpg

from app.domain.entities import Transaction
from app.domain.value_objects import ContextChunk
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import IEmbeddingRepository
from app.application.dto import EmbeddingRecordDTO, VectorSearchRequestDTO
from app.domain.types import EmbeddingSourceType, TransactionStatus, TransactionType


class EmbeddingRepository(IEmbeddingRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def search(self, vector_search_request: VectorSearchRequestDTO) -> List[ContextChunk]:
        async with self._pool.tenant_transaction(vector_search_request.partner_id) as connection:
            records = await connection.fetch(
                """
                    SELECT
                        source_id,
                        source_type,
                        context_text,
                        1 - (vector <=> $3) AS similarity
                    FROM vector_embeddings
                    WHERE partner_id = $1
                        AND user_id = $2
                    ORDER BY vector <=> $3
                    LIMIT $4
                """,
                vector_search_request.partner_id,
                vector_search_request.user_id,
                vector_search_request.query_vector,
                vector_search_request.top_k
            )

        return [
            ContextChunk(
                context_text=record.get("context_text"),
                source_id=UUID(str(record.get("source_id"))),
                source_type=EmbeddingSourceType(record.get("source_type")),
                similarity=Decimal(str(record.get("similarity"))).quantize(Decimal("0.0001"))
            )
            for record in records
        ]

    async def upsert_many(self, partner_id: UUID, records: List[EmbeddingRecordDTO]) -> int:
        if not records:
            return 0

        arguments: List[Tuple[Any, ...]] = [
            (
                record.partner_id,
                record.user_id,
                record.source_type.value,
                record.source_id,
                record.context_text,
                record.vector
            )
            for record in records
        ]

        async with self._pool.tenant_transaction(partner_id) as connection:
            await connection.executemany(
                """
                    INSERT INTO vector_embeddings (
                        partner_id,
                        user_id,
                        source_type,
                        source_id,
                        context_text,
                        vector
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (partner_id, user_id, source_type, source_id)
                    DO UPDATE SET
                        vector = excluded.vector,
                        context_text = excluded.context_text,
                        created_at = now()
                """,
                arguments
            )

        return len(records)

    async def list_stale_transactions(
            self,
            batch_size: int,
            partner_id: UUID,
            user_id: Optional[UUID] = None
    ) -> List[Transaction]:
        conditions = [
            "t.partner_id = $1",
            "t.status <> 'CANCELED'",
            "t.pending_review = false"
        ]

        arguments: List[Any] = [partner_id]

        if user_id is not None:
            arguments.append(user_id)
            conditions.append(f"t.user_id = ${len(arguments)}")

        arguments.append(batch_size)
        limit_placeholder = f"${len(arguments)}"

        async with self._pool.tenant_transaction(partner_id) as connection:
            records = await connection.fetch(
                f"""
                    SELECT
                        t.transaction_id,
                        t.partner_id,
                        t.user_id,
                        t.type,
                        t.amount,
                        t.category,
                        t.description,
                        t.transaction_date,
                        t.due_date,
                        t.status,
                        t.pending_review,
                        t.confidence_score,
                        t.receipt_id,
                        t.created_at,
                        t.updated_at
                    FROM transactions t
                    LEFT JOIN vector_embeddings e
                        ON e.partner_id = t.partner_id
                        AND e.user_id = t.user_id
                        AND e.source_type = 'transaction'
                        AND e.source_id = t.transaction_id
                    WHERE {" AND ".join(conditions)}
                        AND (
                            e.embedding_id IS NULL
                            OR e.created_at < coalesce(t.updated_at, t.created_at)
                        )
                    ORDER BY t.created_at
                    LIMIT {limit_placeholder}
                """,
                *arguments
            )

        return [self._to_entity(record) for record in records]

    @staticmethod
    def _to_entity(record: asyncpg.Record) -> Transaction:
        return Transaction(
            amount=record.get("amount"),
            due_date=record.get("due_date"),
            category=record.get("category"),
            created_at=record.get("created_at"),
            updated_at=record.get("updated_at"),
            description=record.get("description"),
            user_id=UUID(str(record.get("user_id"))),
            type=TransactionType(record.get("type")),
            pending_review=record.get("pending_review"),
            status=TransactionStatus(record.get("status")),
            partner_id=UUID(str(record.get("partner_id"))),
            transaction_date=record.get("transaction_date"),
            confidence_score=record.get("confidence_score"),
            transaction_id=UUID(str(record.get("transaction_id"))),
            receipt_id=UUID(str(record.get("receipt_id"))) if record.get("receipt_id") else None
        )
