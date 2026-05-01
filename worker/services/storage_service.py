import mimetypes
from pathlib import Path

import boto3

from worker.config import WorkerSettings


class S3UploadService:
    def __init__(self, settings: WorkerSettings):
        self.settings = settings
        self.client = boto3.client("s3", region_name=settings.aws_region)

    def upload_video(self, source_path: Path, target_name: str) -> str:
        key = f"{self.settings.s3_prefix}/{target_name}".lstrip("/")
        extra_args = {
            "ContentType": mimetypes.guess_type(source_path.name)[0] or "video/mp4",
        }
        self.client.upload_file(str(source_path), self.settings.s3_bucket, key, ExtraArgs=extra_args)
        return f"s3://{self.settings.s3_bucket}/{key}"
