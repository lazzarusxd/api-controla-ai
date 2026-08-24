import json
from uuid import UUID
from typing import Any, Dict, List, Optional
from datetime import date, datetime, timezone

from app.domain.entities import DataExport
from app.config.logging_setup import logger
from app.infra.cache.redis_client import RedisClient
from app.application.dto import GetDataExportRequestDTO
from app.domain.value_objects import ExportArtifact, ExportScope
from app.application.interfaces import IExportPurger, IExportRegistry
from app.domain.types import ExportFormat, ExportSection, ExportStatus


class RedisExportRegistry(IExportRegistry, IExportPurger):

    def __init__(self, redis_client: RedisClient, retention_seconds: int) -> None:
        self._scan_batch_size = 200
        self._redis_client = redis_client
        self._retention_seconds = retention_seconds

    async def register(self, data_export: DataExport) -> DataExport:
        await self._write(data_export=data_export, ttl_seconds=self._retention_seconds)

        return data_export

    async def find(self, get_data_export_request: GetDataExportRequestDTO) -> Optional[DataExport]:
        raw = await self._redis_client.cache.get(
            self._key(
                user_id=get_data_export_request.user_id,
                export_id=get_data_export_request.export_id,
                partner_id=get_data_export_request.partner_id
            )
        )

        if raw is None:
            return None

        return self._to_entity(payload=json.loads(raw))

    async def save(self, data_export: DataExport) -> DataExport:
        remaining = int((data_export.expires_at - datetime.now(timezone.utc)).total_seconds())

        if remaining <= 0:
            logger.warning(
                "data_export_state_expired",
                export_id=str(data_export.export_id),
                partner_id=str(data_export.partner_id)
            )

            return data_export

        await self._write(data_export=data_export, ttl_seconds=remaining)

        return data_export

    async def purge_user(self, partner_id: UUID, user_id: UUID) -> List[str]:
        keys: List[str] = []
        file_paths: List[str] = []

        async for key in self._redis_client.cache.scan_iter(
                count=self._scan_batch_size,
                match=f"export:{partner_id}:{user_id}:*"
        ):
            keys.append(key)

        for key in keys:
            raw = await self._redis_client.cache.get(key)

            if raw is not None:
                artifact = self._to_entity(payload=json.loads(raw)).artifact

                if artifact is not None:
                    file_paths.append(artifact.file_path)

            await self._redis_client.cache.delete(key)

        logger.info(
            "data_export_state_purged",
            user_id=str(user_id),
            total_keys=len(keys),
            partner_id=str(partner_id),
            total_artifacts=len(file_paths)
        )

        return file_paths

    async def _write(self, data_export: DataExport, ttl_seconds: int) -> None:
        await self._redis_client.cache.set(
            name=self._key(
                user_id=data_export.user_id,
                export_id=data_export.export_id,
                partner_id=data_export.partner_id
            ),
            ex=ttl_seconds,
            value=json.dumps(self._to_payload(data_export=data_export), ensure_ascii=False)
        )

    @staticmethod
    def _key(partner_id: UUID, user_id: UUID, export_id: UUID) -> str:
        return f"export:{partner_id}:{user_id}:{export_id}"

    @staticmethod
    def _to_payload(data_export: DataExport) -> Dict[str, Any]:
        artifact = data_export.artifact
        scope = data_export.scope

        return {
            "status": data_export.status.value,
            "user_id": str(data_export.user_id),
            "export_id": str(data_export.export_id),
            "partner_id": str(data_export.partner_id),
            "failure_reason": data_export.failure_reason,
            "export_format": data_export.export_format.value,
            "expires_at": data_export.expires_at.isoformat(),
            "requested_at": data_export.requested_at.isoformat(),
            "completed_at": (
                data_export.completed_at.isoformat() if data_export.completed_at is not None else None
            ),
            "scope": {
                "sections": [section.value for section in scope.ordered_sections],
                "end_date": scope.end_date.isoformat() if scope.end_date is not None else None,
                "start_date": scope.start_date.isoformat() if scope.start_date is not None else None
            },
            "artifact": None if artifact is None else {
                "checksum": artifact.checksum,
                "file_path": artifact.file_path,
                "truncated": artifact.truncated,
                "file_name": artifact.file_name,
                "byte_size": artifact.byte_size,
                "media_type": artifact.media_type,
                "total_records": artifact.total_records
            }
        }

    @staticmethod
    def _to_entity(payload: Dict[str, Any]) -> DataExport:
        completed_at: Optional[str] = payload.get("completed_at")
        scope_payload: Dict[str, Any] = payload.get("scope") or {}
        artifact_payload: Optional[Dict[str, Any]] = payload.get("artifact")

        end_date: Optional[str] = scope_payload.get("end_date")
        start_date: Optional[str] = scope_payload.get("start_date")

        scope = ExportScope(
            end_date=date.fromisoformat(end_date) if end_date is not None else None,
            start_date=date.fromisoformat(start_date) if start_date is not None else None,
            sections=frozenset(
                ExportSection(section) for section in scope_payload.get("sections") or []
            )
        )

        return DataExport(
            scope=scope,
            user_id=UUID(payload.get("user_id")),
            export_id=UUID(payload.get("export_id")),
            partner_id=UUID(payload.get("partner_id")),
            status=ExportStatus(payload.get("status")),
            failure_reason=payload.get("failure_reason"),
            export_format=ExportFormat(payload.get("export_format")),
            expires_at=datetime.fromisoformat(payload.get("expires_at")),
            requested_at=datetime.fromisoformat(payload.get("requested_at")),
            completed_at=datetime.fromisoformat(completed_at) if completed_at is not None else None,
            artifact=None if artifact_payload is None else ExportArtifact(
                checksum=artifact_payload.get("checksum"),
                file_path=artifact_payload.get("file_path"),
                file_name=artifact_payload.get("file_name"),
                byte_size=artifact_payload.get("byte_size"),
                truncated=artifact_payload.get("truncated"),
                media_type=artifact_payload.get("media_type"),
                total_records=artifact_payload.get("total_records")
            )
        )
