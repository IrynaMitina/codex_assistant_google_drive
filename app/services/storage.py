# app/services/storage.py
import os

import aiofiles
from fastapi import UploadFile

from app.core.config import get_settings


settings = get_settings()
STORAGE_DIR = settings.storage_dir


async def save_upload_file(upload_file: UploadFile, storage_key: str) -> int:
    os.makedirs(os.path.dirname(storage_key), exist_ok=True)

    size = 0

    async with aiofiles.open(storage_key, "wb") as out_file:
        while chunk := await upload_file.read(1024 * 1024):
            size += len(chunk)
            await out_file.write(chunk)

    return size


async def delete_storage_file(storage_key: str) -> None:
    if os.path.exists(storage_key):
        os.remove(storage_key)
