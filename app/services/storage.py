# app/services/storage.py
import asyncio
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import aiofiles
from fastapi import UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.core.config import get_settings


settings = get_settings()
STORAGE_DIR = settings.storage_dir


class StorageBackend(ABC):
    @abstractmethod
    async def save_upload_file(self, upload_file: UploadFile, storage_key: str) -> int:
        raise NotImplementedError

    @abstractmethod
    async def delete_storage_file(self, storage_key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def exists(self, storage_key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def download_response(
        self,
        storage_key: str,
        filename: str,
        media_type: str,
    ) -> Response:
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    def __init__(self, storage_dir: str) -> None:
        self.storage_dir = storage_dir

    def _path_for_key(self, storage_key: str) -> str:
        if os.path.isabs(storage_key):
            return storage_key

        normalized_key = os.path.normpath(storage_key)
        normalized_storage_dir = os.path.normpath(self.storage_dir)

        if (
            normalized_key == normalized_storage_dir
            or normalized_key.startswith(normalized_storage_dir + os.sep)
        ):
            return storage_key

        absolute_key = os.path.abspath(storage_key)
        absolute_storage_dir = os.path.abspath(self.storage_dir)
        if os.path.commonpath([absolute_key, absolute_storage_dir]) == absolute_storage_dir:
            return storage_key

        return os.path.join(self.storage_dir, storage_key)

    async def save_upload_file(self, upload_file: UploadFile, storage_key: str) -> int:
        path = self._path_for_key(storage_key)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        size = 0
        await upload_file.seek(0)

        async with aiofiles.open(path, "wb") as out_file:
            while chunk := await upload_file.read(1024 * 1024):
                size += len(chunk)
                await out_file.write(chunk)

        return size

    async def delete_storage_file(self, storage_key: str) -> None:
        path = self._path_for_key(storage_key)
        if os.path.exists(path):
            os.remove(path)

    async def exists(self, storage_key: str) -> bool:
        return os.path.exists(self._path_for_key(storage_key))

    async def download_response(
        self,
        storage_key: str,
        filename: str,
        media_type: str,
    ) -> Response:
        return FileResponse(
            path=self._path_for_key(storage_key),
            filename=filename,
            media_type=media_type,
        )


class S3StorageBackend(StorageBackend):
    def __init__(
        self,
        bucket_name: str,
        region_name: str | None = None,
        endpoint_url: str | None = None,
        client=None,
    ) -> None:
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.endpoint_url = endpoint_url
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                region_name=self.region_name,
                endpoint_url=self.endpoint_url,
            )
        return self._client

    async def save_upload_file(self, upload_file: UploadFile, storage_key: str) -> int:
        await upload_file.seek(0)
        size = await asyncio.to_thread(self._file_size, upload_file.file)
        await upload_file.seek(0)

        await asyncio.to_thread(
            self.client.upload_fileobj,
            upload_file.file,
            self.bucket_name,
            storage_key,
            ExtraArgs={"ContentType": upload_file.content_type or "application/octet-stream"},
        )

        return size

    async def delete_storage_file(self, storage_key: str) -> None:
        await asyncio.to_thread(
            self.client.delete_object,
            Bucket=self.bucket_name,
            Key=storage_key,
        )

    async def exists(self, storage_key: str) -> bool:
        try:
            await asyncio.to_thread(
                self.client.head_object,
                Bucket=self.bucket_name,
                Key=storage_key,
            )
        except Exception as exc:
            response = getattr(exc, "response", {})
            status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            error_code = response.get("Error", {}).get("Code")
            if status_code == 404 or error_code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

        return True

    async def download_response(
        self,
        storage_key: str,
        filename: str,
        media_type: str,
    ) -> Response:
        obj = await asyncio.to_thread(
            self.client.get_object,
            Bucket=self.bucket_name,
            Key=storage_key,
        )
        body = obj["Body"]

        return StreamingResponse(
            self._body_iterator(body),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @staticmethod
    def _file_size(file_obj) -> int:
        position = file_obj.tell()
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(position)
        return size

    @staticmethod
    async def _body_iterator(body) -> AsyncIterator[bytes]:
        try:
            while chunk := await asyncio.to_thread(body.read, 1024 * 1024):
                yield chunk
        finally:
            close = getattr(body, "close", None)
            if close:
                await asyncio.to_thread(close)


def get_storage_backend() -> StorageBackend:
    backend = settings.storage_backend.lower()

    if backend == "local":
        return LocalStorageBackend(STORAGE_DIR)

    if backend == "s3":
        if not settings.s3_bucket_name:
            raise RuntimeError("S3_BUCKET_NAME must be set when STORAGE_BACKEND=s3")
        return S3StorageBackend(
            bucket_name=settings.s3_bucket_name,
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
        )

    raise RuntimeError(f"Unsupported storage backend: {settings.storage_backend}")


async def save_upload_file(upload_file: UploadFile, storage_key: str) -> int:
    return await get_storage_backend().save_upload_file(upload_file, storage_key)


async def delete_storage_file(storage_key: str) -> None:
    await get_storage_backend().delete_storage_file(storage_key)


async def storage_file_exists(storage_key: str) -> bool:
    return await get_storage_backend().exists(storage_key)


async def storage_download_response(
    storage_key: str,
    filename: str,
    media_type: str,
) -> Response:
    return await get_storage_backend().download_response(storage_key, filename, media_type)
