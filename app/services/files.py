# app/services/files.py
import os
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.user import User
from app.services.access import has_access
from app.services.storage import STORAGE_DIR, save_upload_file, delete_storage_file


async def upload_file(
    db: AsyncSession,
    current_user: User,
    folder_id: int,
    upload: UploadFile,
) -> File:
    allowed = await has_access(
        db=db,
        user=current_user,
        resource_type="folder",
        resource_id=folder_id,
        min_role="editor",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="No access to folder")

    file_uuid = str(uuid.uuid4())

    storage_key = os.path.join(
        STORAGE_DIR,
        str(current_user.id),
        file_uuid,
        upload.filename or "uploaded_file",
    )

    size_bytes = await save_upload_file(upload, storage_key)

    db_file = File(
        owner_id=current_user.id,
        folder_id=folder_id,
        name=upload.filename or "uploaded_file",
        mime_type=upload.content_type or "application/octet-stream",
        size_bytes=size_bytes,
        storage_key=storage_key,
        checksum=None,
    )

    db.add(db_file)
    await db.commit()
    await db.refresh(db_file)

    return db_file


async def get_file_for_download(
    db: AsyncSession,
    current_user: User,
    file_id: int,
) -> File:
    allowed = await has_access(
        db=db,
        user=current_user,
        resource_type="file",
        resource_id=file_id,
        min_role="viewer",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="No access to file")

    db_file = await db.get(File, file_id)

    if not db_file or db_file.deleted_at:
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.exists(db_file.storage_key):
        raise HTTPException(status_code=404, detail="Stored file missing")

    return db_file


async def delete_file(
    db: AsyncSession,
    current_user: User,
    file_id: int,
) -> None:
    allowed = await has_access(
        db=db,
        user=current_user,
        resource_type="file",
        resource_id=file_id,
        min_role="editor",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="No access to file")

    db_file = await db.get(File, file_id)

    if not db_file or db_file.deleted_at:
        raise HTTPException(status_code=404, detail="File not found")

    await delete_storage_file(db_file.storage_key)

    from sqlalchemy import func

    db_file.deleted_at = func.now()

    await db.commit()
