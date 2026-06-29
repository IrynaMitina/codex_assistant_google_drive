# app/services/folders.py
from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder
from app.models.file import File
from app.models.user import User
from app.services.access import has_access
from app.schemas.drive import FolderCreate


async def create_folder(
    db: AsyncSession,
    current_user: User,
    payload: FolderCreate,
) -> Folder:
    if payload.parent_id is not None:
        allowed = await has_access(
            db=db,
            user=current_user,
            resource_type="folder",
            resource_id=payload.parent_id,
            min_role="editor",
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="No access to parent folder")

    folder = Folder(
        owner_id=current_user.id,
        parent_id=payload.parent_id,
        name=payload.name,
    )

    db.add(folder)
    await db.commit()
    await db.refresh(folder)

    return folder


async def list_folder_contents(
    db: AsyncSession,
    current_user: User,
    folder_id: int,
) -> dict:
    allowed = await has_access(
        db=db,
        user=current_user,
        resource_type="folder",
        resource_id=folder_id,
        min_role="viewer",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="No access to folder")

    folders = (
        await db.scalars(
            select(Folder).where(
                Folder.parent_id == folder_id,
                Folder.deleted_at.is_(None),
            )
        )
    ).all()

    files = (
        await db.scalars(
            select(File).where(
                File.folder_id == folder_id,
                File.deleted_at.is_(None),
            )
        )
    ).all()

    return {
        "folders": folders,
        "files": files,
    }


async def delete_folder(
    db: AsyncSession,
    current_user: User,
    folder_id: int,
) -> None:
    allowed = await has_access(
        db=db,
        user=current_user,
        resource_type="folder",
        resource_id=folder_id,
        min_role="editor",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="No access to folder")

    folder = await db.get(Folder, folder_id)
    if not folder or folder.deleted_at:
        raise HTTPException(status_code=404, detail="Folder not found")

    folder.deleted_at = func.now()

    await db.execute(
        update(File)
        .where(File.folder_id == folder_id)
        .values(deleted_at=func.now())
    )

    await db.execute(
        update(Folder)
        .where(Folder.parent_id == folder_id)
        .values(deleted_at=func.now())
    )

    await db.commit()
