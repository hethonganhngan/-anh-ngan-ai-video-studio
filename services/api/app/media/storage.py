"""Object Storage: LocalStorage (dev/test) và S3Storage (MinIO / S3-compatible)."""
import os
import shutil
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings


class StorageBackend(ABC):
    name = "abstract"

    @abstractmethod
    def put_file(self, key: str, src_path: str, content_type: str) -> None: ...

    @abstractmethod
    def get_to_path(self, key: str, dst_path: str) -> None: ...

    @abstractmethod
    def open(self, key: str) -> BinaryIO: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    def local_path(self, key: str) -> str | None:
        return None

    def presigned_url(self, key: str, expires: int = 3600) -> str | None:
        return None

    @abstractmethod
    def health(self) -> dict: ...


class LocalStorage(StorageBackend):
    name = "local"

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("Storage key không hợp lệ")
        return p

    def put_file(self, key, src_path, content_type):
        dst = self._path(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_path, dst)

    def get_to_path(self, key, dst_path):
        shutil.copyfile(self._path(key), dst_path)

    def open(self, key):
        return open(self._path(key), "rb")

    def delete(self, key):
        p = self._path(key)
        if p.exists():
            p.unlink()

    def exists(self, key):
        return self._path(key).exists()

    def local_path(self, key):
        return str(self._path(key))

    def health(self):
        probe = self.root / ".health"
        try:
            probe.write_text("ok")
            probe.unlink()
            free = shutil.disk_usage(self.root).free
            return {"ok": True, "backend": "local", "free_gb": round(free / 1e9, 1)}
        except OSError as e:
            return {"ok": False, "backend": "local", "error": str(e)}


class S3Storage(StorageBackend):
    name = "s3"

    def __init__(self):
        import boto3

        s = get_settings()
        self.bucket = s.s3_bucket
        self.client = boto3.client(
            "s3", endpoint_url=s.s3_endpoint_url, aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key, region_name=s.s3_region,
        )

    def ensure_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def put_file(self, key, src_path, content_type):
        self.client.upload_file(src_path, self.bucket, key, ExtraArgs={"ContentType": content_type})

    def get_to_path(self, key, dst_path):
        self.client.download_file(self.bucket, key, dst_path)

    def open(self, key):
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"]

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def presigned_url(self, key, expires=3600):
        return self.client.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires)

    def health(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return {"ok": True, "backend": "s3", "bucket": self.bucket}
        except Exception as e:
            return {"ok": False, "backend": "s3", "error": str(e)[:200]}


@lru_cache
def get_storage() -> StorageBackend:
    s = get_settings()
    if s.storage_backend == "s3":
        st = S3Storage()
        try:
            st.ensure_bucket()
        except Exception:
            pass
        return st
    return LocalStorage(s.storage_local_root)


def reset_storage() -> None:
    get_storage.cache_clear()


def tmp_dir() -> str:
    d = Path(get_settings().storage_local_root).parent / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
