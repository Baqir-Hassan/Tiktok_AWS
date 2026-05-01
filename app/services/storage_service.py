import shutil
from abc import ABC, abstractmethod
from pathlib import Path

import boto3

from app.core.config import get_settings


class StorageService(ABC):
    @abstractmethod
    def store_video(self, source_path: Path, target_name: str) -> str:
        raise NotImplementedError


class LocalStorageService(StorageService):
    def __init__(self) -> None:
        self.settings = get_settings()

    def store_video(self, source_path: Path, target_name: str) -> str:
        destination = self.settings.local_storage_path / target_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        return f"{self.settings.public_media_base_url.rstrip('/')}/{destination.name}"


class S3StorageService(StorageService):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.s3_bucket_name:
            raise RuntimeError("S3 bucket is not configured")
        self.settings = settings
        self.client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    def store_video(self, source_path: Path, target_name: str) -> str:
        self.client.upload_file(str(source_path), self.settings.s3_bucket_name, target_name)
        return f"https://{self.settings.s3_bucket_name}.s3.{self.settings.aws_region}.amazonaws.com/{target_name}"


class StorageFactory:
    @staticmethod
    def create() -> StorageService:
        settings = get_settings()
        if settings.storage_backend.lower() == "s3":
            return S3StorageService()
        return LocalStorageService()
