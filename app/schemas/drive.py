# app/schemas/drive.py
from pydantic import BaseModel


class FolderCreate(BaseModel):
    name: str
    parent_id: int | None = None


class FolderRead(BaseModel):
    id: int
    name: str
    parent_id: int | None

    model_config = {"from_attributes": True}


class FileRead(BaseModel):
    id: int
    name: str
    mime_type: str
    size_bytes: int
    folder_id: int

    model_config = {"from_attributes": True}


class FolderContents(BaseModel):
    folders: list[FolderRead]
    files: list[FileRead]


class ShareCreate(BaseModel):
    user_id: int
    role: str  # viewer / editor


class PermissionRead(BaseModel):
    id: int
    user_id: int
    resource_type: str
    resource_id: int
    role: str

    model_config = {"from_attributes": True}