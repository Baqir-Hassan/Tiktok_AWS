import shutil
from abc import ABC, abstractmethod
from pathlib import Path

import boto3

from app.core.config import get_settings


class StorageService(ABC):
    @abstractmethod
    def store_video(self, source_path: Path, target_name: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def check_connection(self) -> dict[str, object]:
        raise NotImplementedError

    def _validate_source_path(self, source_path: Path) -> Path:
        candidate = source_path.resolve()
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError(f"Source video not found: {source_path}")
        return candidate

    def _sanitize_target_name(self, target_name: str) -> str:
        normalized = target_name.replace("\\", "/").strip("/")
        if not normalized:
            raise ValueError("Storage target name must not be empty")
        path = Path(normalized)
        if any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError(f"Unsafe storage target name: {target_name}")
        return "/".join(path.parts)


class LocalStorageService(StorageService):
    def __init__(self) -> None:
        self.settings = get_settings()

    def store_video(self, source_path: Path, target_name: str) -> str:
        source = self._validate_source_path(source_path)
        safe_target_name = self._sanitize_target_name(target_name)
        destination = self._resolve_local_target(safe_target_name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        relative_path = destination.relative_to(self.settings.local_storage_path).as_posix()
        return f"local://{relative_path}"

    def check_connection(self) -> dict[str, object]:
        base_path = self.settings.local_storage_path.resolve()
        try:
            base_path.mkdir(parents=True, exist_ok=True)
            probe_dir = base_path / ".healthcheck"
            probe_dir.mkdir(parents=True, exist_ok=True)
            probe_file = probe_dir / "write_test.tmp"
            probe_file.write_text("ok", encoding="utf-8")
            probe_file.unlink(missing_ok=True)
            return {"provider": "local", "ready": True, "base_path": str(base_path)}
        except Exception as exc:
            return {
                "provider": "local",
                "ready": False,
                "base_path": str(base_path),
                "detail": str(exc),
            }

    def _resolve_local_target(self, target_name: str) -> Path:
        base_path = self.settings.local_storage_path.resolve()
        destination = (base_path / Path(target_name)).resolve()
        if destination != base_path and base_path not in destination.parents:
            raise ValueError(f"Unsafe local storage target: {target_name}")
        return destination


class S3StorageService(StorageService):
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        client_kwargs: dict[str, str] = {"region_name": settings.aws_region}
        if settings.aws_access_key_id:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
        if settings.aws_secret_access_key:
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_s3_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_s3_endpoint_url
        self.client = boto3.client("s3", **client_kwargs)

    def store_video(self, source_path: Path, target_name: str) -> str:
        if not self.settings.s3_bucket_name:
            raise RuntimeError("S3 bucket is not configured")
        source = self._validate_source_path(source_path)
        safe_target_name = self._sanitize_target_name(target_name)
        self.client.upload_file(str(source), self.settings.s3_bucket_name, safe_target_name)
        return f"s3://{self.settings.s3_bucket_name}/{safe_target_name}"

    def check_connection(self) -> dict[str, object]:
        bucket = self.settings.s3_bucket_name
        if not bucket:
            return {
                "provider": "s3",
                "ready": False,
                "detail": "S3 bucket is not configured",
            }
        try:
            self.client.head_bucket(Bucket=bucket)
            return {"provider": "s3", "ready": True, "bucket": bucket}
        except Exception as exc:
            return {
                "provider": "s3",
                "ready": False,
                "bucket": bucket,
                "detail": str(exc),
            }


class StorageFactory:
    @staticmethod
    def create() -> StorageService:
        settings = get_settings()
        if settings.storage_backend.lower() == "s3":
            return S3StorageService()
        return LocalStorageService()
