# app/services/access.py

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.folder import Folder
from app.models.permission import Permission
from app.models.user import User

# access check mostly for endpoints
async def has_access(
    db: AsyncSession,
    user: User,
    resource_type: str,
    resource_id: int,
    min_role: str = "viewer",
) -> bool:
    if resource_type == "folder":
        resource = await db.get(Folder, resource_id)
    else:
        resource = await db.get(File, resource_id)

    if not resource or resource.deleted_at:
        return False

    if resource.owner_id == user.id:
        return True

    result = await db.scalars(
        select(Permission).where(
            Permission.user_id == user.id,
            Permission.resource_type == resource_type,
            Permission.resource_id == resource_id,
        )
    )

    permission = result.first()

    if not permission:
        return False

    if min_role == "viewer":
        return permission.role in {"viewer", "editor"}

    if min_role == "editor":
        return permission.role == "editor"

    return False
