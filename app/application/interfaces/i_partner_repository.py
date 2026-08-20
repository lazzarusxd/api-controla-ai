from uuid import UUID
from typing import List, Protocol


class IPartnerRepository(Protocol):

    async def list_active_ids(self) -> List[UUID]:
        """Parceiros ativos, base da varredura de indexação por tenant."""
        ...
