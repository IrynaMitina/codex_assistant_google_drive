from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.folder import Folder
from app.models.permission import Permission
from app.models.user import User
from app.schemas.drive import ShareCreate
from app.services.access import has_access


async def share_resource(
    db: AsyncSession,
    current_user: User,
    resource_type: str,
    resource_id: int,
    payload: ShareCreate,
) -> Permission:
    if resource_type not in {"file", "folder"}:
        raise HTTPException(status_code=400, detail="Invalid resource type")

    if payload.role not in {"viewer", "editor"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    allowed = await has_access(
        db=db,
        user=current_user,
        resource_type=resource_type,
        resource_id=resource_id,
        min_role="editor",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="No permission to share")

    target_user = await db.get(User, payload.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    if resource_type == "file":
        resource = await db.get(File, resource_id)
    else:
        resource = await db.get(Folder, resource_id)

    if not resource or resource.deleted_at:
        raise HTTPException(status_code=404, detail="Resource not found")

    if resource.owner_id == payload.user_id:
        raise HTTPException(status_code=400, detail="User already owns this resource")

    existing = (
        await db.scalars(
            select(Permission).where(
                Permission.user_id == payload.user_id,
                Permission.resource_type == resource_type,
                Permission.resource_id == resource_id,
            )
        )
    ).first()

    if existing:
        existing.role = payload.role
        permission = existing
    else:
        permission = Permission(
            user_id=payload.user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            role=payload.role,
        )
        db.add(permission)

    await db.commit()
    await db.refresh(permission)

    return permission


async def remove_permission(
    db: AsyncSession,
    current_user: User,
    permission_id: int,
) -> None:
    permission = await db.get(Permission, permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")

    allowed = await has_access(
        db=db,
        user=current_user,
        resource_type=permission.resource_type,
        resource_id=permission.resource_id,
        min_role="editor",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="No permission to modify sharing")

    await db.delete(permission)
    await db.commit()


async def list_permissions(
    db: AsyncSession,
    current_user: User,
    resource_type: str,
    resource_id: int,
) -> list[Permission]:
    if resource_type not in {"file", "folder"}:
        raise HTTPException(status_code=400, detail="Invalid resource type")

    allowed = await has_access(
        db=db,
        user=current_user,
        resource_type=resource_type,
        resource_id=resource_id,
        min_role="editor",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="No permission to view sharing")

    permissions = (
        await db.scalars(
            select(Permission).where(
                Permission.resource_type == resource_type,
                Permission.resource_id == resource_id,
            )
        )
    ).all()

    return list(permissions)
