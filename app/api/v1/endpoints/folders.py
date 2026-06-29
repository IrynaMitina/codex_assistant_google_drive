# app/api/v1/endpoints/folders.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.drive import FolderCreate, FolderRead, FolderContents
from app.services import folders as folder_service

router = APIRouter(prefix="/folders", tags=["folders"])


@router.post("", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
async def create_folder(
    payload: FolderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await folder_service.create_folder(
        db=db,
        current_user=current_user,
        payload=payload,
    )


@router.get("/{folder_id}/contents", response_model=FolderContents)
async def list_folder_contents(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await folder_service.list_folder_contents(
        db=db,
        current_user=current_user,
        folder_id=folder_id,
    )


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await folder_service.delete_folder(
        db=db,
        current_user=current_user,
        folder_id=folder_id,
    )
    return None


