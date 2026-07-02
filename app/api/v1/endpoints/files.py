# app/api/v1/endpoints/files.py
from fastapi import APIRouter, Depends, File as UploadFileParam, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.drive import FileRead, SharedLinkRead
from app.services import files as file_service

router = APIRouter(tags=["files"])


@router.post(
    "/folders/{folder_id}/files",
    response_model=FileRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    folder_id: int,
    upload: UploadFile = UploadFileParam(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await file_service.upload_file(
        db=db,
        current_user=current_user,
        folder_id=folder_id,
        upload=upload,
    )


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_file = await file_service.get_file_for_download(
        db=db,
        current_user=current_user,
        file_id=file_id,
    )

    return FileResponse(
        path=db_file.storage_key,
        filename=db_file.name,
        media_type=db_file.mime_type,
    )


@router.post("/files/{file_id}/shared-link", response_model=SharedLinkRead)
async def create_shared_link(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token = await file_service.create_shared_link(
        db=db,
        current_user=current_user,
        file_id=file_id,
    )

    return SharedLinkRead(
        token=token,
        url_path=f"/api/v1/drive/shared-links/{token}/download",
    )


@router.get("/shared-links/{token}/download")
async def download_shared_link(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    db_file = await file_service.get_file_for_shared_link_download(
        db=db,
        token=token,
    )

    return FileResponse(
        path=db_file.storage_key,
        filename=db_file.name,
        media_type=db_file.mime_type,
    )


@router.delete("/files/{file_id}/shared-link", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_shared_link(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await file_service.revoke_shared_link(
        db=db,
        current_user=current_user,
        file_id=file_id,
    )
    return None


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await file_service.delete_file(
        db=db,
        current_user=current_user,
        file_id=file_id,
    )
    return None
