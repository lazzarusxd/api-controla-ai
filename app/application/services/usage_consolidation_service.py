from app.config.logging_setup import logger
from app.application.interfaces import IMeteringRepository, IUsageBuffer
from app.application.dto import UsageConsolidationRequestDTO, UsageConsolidationResultDTO


class UsageConsolidationService:

    def __init__(self, usage_buffer: IUsageBuffer, metering_repository: IMeteringRepository) -> None:
        self._usage_buffer = usage_buffer
        self._metering_repository = metering_repository

    async def consolidate(
            self,
            usage_consolidation_request: UsageConsolidationRequestDTO
    ) -> UsageConsolidationResultDTO:
        claims = await self._usage_buffer.claim(usage_consolidation_request=usage_consolidation_request)

        applied = 0
        replayed = 0

        for claimed_usage in claims:
            if await self._metering_repository.apply(claimed_usage=claimed_usage):
                applied += 1
            else:
                replayed += 1

            await self._usage_buffer.acknowledge(claimed_usage=claimed_usage)

        if claims:
            scoped_partner = usage_consolidation_request.partner_id

            logger.info(
                "usage_consolidated",
                applied=applied,
                replayed=replayed,
                claimed=len(claims),
                partner_id=str(scoped_partner) if scoped_partner is not None else None
            )

        return UsageConsolidationResultDTO(claimed=len(claims), applied=applied, replayed=replayed)
