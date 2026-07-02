import secrets
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.user import User
from app.services.access import has_access
from app.services.storage import delete_storage_file, save_upload_file, storage_file_exists


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

    filename = upload.filename or "uploaded_file"
    storage_key = f"{current_user.id}/{file_uuid}/{filename}"

    size_bytes = await save_upload_file(upload, storage_key)

    db_file = File(
        owner_id=current_user.id,
        folder_id=folder_id,
        name=filename,
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

    if not await storage_file_exists(db_file.storage_key):
        raise HTTPException(status_code=404, detail="Stored file missing")

    return db_file


async def create_shared_link(
    db: AsyncSession,
    current_user: User,
    file_id: int,
) -> str:
    db_file = await db.get(File, file_id)

    if not db_file or db_file.deleted_at:
        raise HTTPException(status_code=404, detail="File not found")

    if db_file.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only file owner can share link")

    if not db_file.shared_link_token:
        db_file.shared_link_token = secrets.token_urlsafe(32)
        await db.commit()
        await db.refresh(db_file)

    return db_file.shared_link_token


async def get_file_for_shared_link_download(
    db: AsyncSession,
    token: str,
) -> File:
    from sqlalchemy import select

    result = await db.scalars(
        select(File).where(
            File.shared_link_token == token,
        )
    )
    db_file = result.first()

    if not db_file or db_file.deleted_at:
        raise HTTPException(status_code=404, detail="Shared link not found")

    if not await storage_file_exists(db_file.storage_key):
        raise HTTPException(status_code=404, detail="Stored file missing")

    return db_file


async def revoke_shared_link(
    db: AsyncSession,
    current_user: User,
    file_id: int,
) -> None:
    db_file = await db.get(File, file_id)

    if not db_file or db_file.deleted_at:
        raise HTTPException(status_code=404, detail="File not found")

    if db_file.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only file owner can revoke shared link")

    db_file.shared_link_token = None
    await db.commit()


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
