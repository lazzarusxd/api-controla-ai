from typing import Any, Dict

from app.config.logging_setup import logger
from app.config.settings import ServiceSettings
from app.infra.database.postgres import PostgresPool
from app.application.dto import IndexUserContextRequestDTO
from app.infra.repositories.partner_repository import PartnerRepository
from app.infra.queue.tasks.index_user_context import build_indexing_service


async def index_pending_context(ctx: Dict[str, Any]) -> int:
    """Varredura periódica do contexto ainda não vetorizado."""
    postgres: PostgresPool = ctx.get("postgres")
    settings: ServiceSettings = ctx.get("settings")

    partner_repository = PartnerRepository(postgres)
    indexing_service = build_indexing_service(postgres=postgres, settings=settings)

    partner_ids = await partner_repository.list_active_ids()

    total_indexed = 0

    for partner_id in partner_ids:
        result = await indexing_service.index(
            index_user_context_request=IndexUserContextRequestDTO(
                partner_id=partner_id,
                batch_size=settings.RAG_INDEX_BATCH_SIZE
            )
        )

        total_indexed += result.indexed

    logger.info("assistant_indexing_sweep_finished", partners=len(partner_ids), indexed=total_indexed)

    return total_indexed
