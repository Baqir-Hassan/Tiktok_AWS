from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.client import BaseClient
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.security import create_media_access_token, decode_media_access_token
from app.models.job import Job, JobStatus
from app.models.user import User


@dataclass(frozen=True)
class MediaAccessDescriptor:
    kind: str
    value: str
    expires_in_seconds: int | None


class MediaAccessService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._s3_client: BaseClient | None = None

    def create_user_access_descriptor(self, job: Job, current_user: User) -> MediaAccessDescriptor:
        if job.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if job.status != JobStatus.COMPLETED.value:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Video is not ready yet")

        locator = self._get_locator(job)
        if locator.startswith("s3://"):
            return MediaAccessDescriptor(
                kind="remote",
                value=self._create_presigned_s3_url(locator),
                expires_in_seconds=self.settings.media_access_token_expire_seconds,
            )
        if locator.startswith("http://") or locator.startswith("https://"):
            return MediaAccessDescriptor(kind="remote", value=locator, expires_in_seconds=None)

        token = create_media_access_token(job_id=job.id, user_id=current_user.id)
        return MediaAccessDescriptor(kind="local", value=token, expires_in_seconds=self.settings.media_access_token_expire_seconds)

    def resolve_local_media_path(self, job: Job, token: str) -> Path:
        payload = decode_media_access_token(token)
        if int(payload["sub"]) != job.user_id or int(payload["job_id"]) != job.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid media access token")
        locator = self._get_locator(job)
        return self._resolve_local_locator(locator)

    def _get_locator(self, job: Job) -> str:
        locator = (job.uploaded_video_url or job.video_url or "").strip()
        if not locator:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video asset not found")
        return locator

    def _resolve_local_locator(self, locator: str) -> Path:
        relative_path = locator
        if locator.startswith("local://"):
            relative_path = locator[len("local://") :]
        elif locator.startswith(self.settings.public_media_base_url.rstrip("/") + "/"):
            relative_path = locator[len(self.settings.public_media_base_url.rstrip("/") + "/") :]

        base_path = self.settings.local_storage_path.resolve()
        candidate = (base_path / Path(relative_path)).resolve()
        if candidate != base_path and base_path not in candidate.parents:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsafe local media path")
        if not candidate.exists() or not candidate.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local media file not found")
        return candidate

    def _create_presigned_s3_url(self, locator: str) -> str:
        bucket, key = self._parse_s3_locator(locator)
        return self._get_s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=self.settings.media_access_token_expire_seconds,
        )

    @staticmethod
    def _parse_s3_locator(locator: str) -> tuple[str, str]:
        remainder = locator[len("s3://") :]
        bucket, _, key = remainder.partition("/")
        if not bucket or not key:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid S3 media locator")
        return bucket, key

    def _get_s3_client(self) -> BaseClient:
        if self._s3_client is not None:
            return self._s3_client
        client_kwargs: dict[str, str] = {"region_name": self.settings.aws_region}
        if self.settings.aws_access_key_id:
            client_kwargs["aws_access_key_id"] = self.settings.aws_access_key_id
        if self.settings.aws_secret_access_key:
            client_kwargs["aws_secret_access_key"] = self.settings.aws_secret_access_key
        if self.settings.aws_s3_endpoint_url:
            client_kwargs["endpoint_url"] = self.settings.aws_s3_endpoint_url
        self._s3_client = boto3.client("s3", **client_kwargs)
        return self._s3_client
