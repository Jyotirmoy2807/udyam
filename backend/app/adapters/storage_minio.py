from typing import Any
import boto3
from botocore.client import Config
from app.config import settings
from app.ports import StoragePort


class MinioStorageAdapter:
    """Object storage adapter for MinIO implementing StoragePort."""

    def __init__(self):
        protocol = "https" if settings.MINIO_SECURE else "http"
        self.endpoint_url = f"{protocol}://{settings.MINIO_ENDPOINT}"
        self.bucket = settings.MINIO_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except Exception:
                pass

    def put_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def get_bytes(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def generate_presigned_url(self, key: str, ttl_seconds: int = 300) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )

    def delete_object(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)
