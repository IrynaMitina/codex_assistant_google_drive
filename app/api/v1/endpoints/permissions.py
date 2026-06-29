from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.drive import PermissionRead, ShareCreate
from app.services import permissions as permission_service

router = APIRouter(tags=["permissions"])


@router.post(
    "/{resource_type}/{resource_id}/share",
    response_model=PermissionRead,
    status_code=status.HTTP_201_CREATED,
)
async def share_resource(
    resource_type: str,
    resource_id: int,
    payload: ShareCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await permission_service.share_resource(
        db=db,
        current_user=current_user,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
    )


@router.get(
    "/{resource_type}/{resource_id}/permissions",
    response_model=list[PermissionRead],
)
async def list_permissions(
    resource_type: str,
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await permission_service.list_permissions(
        db=db,
        current_user=current_user,
        resource_type=resource_type,
        resource_id=resource_id,
    )


@router.delete(
    "/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_permission(
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await permission_service.remove_permission(
        db=db,
        current_user=current_user,
        permission_id=permission_id,
    )
    return None