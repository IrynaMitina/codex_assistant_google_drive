import os

import pytest
from fastapi import HTTPException
from jose import jwt

from app.api.deps import get_current_user
from app.core import security
from app.models.file import File
from app.models.folder import Folder
from app.models.permission import Permission
from app.models.user import User
from app.schemas.drive import FolderCreate, ShareCreate
from app.services import files as file_service
from app.services import folders as folder_service
from app.services import permissions as permission_service


async def create_folder_record(db, owner_id: int, name: str = "docs", parent_id=None):
    folder = Folder(owner_id=owner_id, parent_id=parent_id, name=name)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


async def create_file_record(db, owner_id: int, folder_id: int, storage_key: str):
    db_file = File(
        owner_id=owner_id,
        folder_id=folder_id,
        name=os.path.basename(storage_key),
        mime_type="text/plain",
        size_bytes=5,
        storage_key=storage_key,
        checksum=None,
    )
    db.add(db_file)
    await db.commit()
    await db.refresh(db_file)
    return db_file


@pytest.mark.asyncio
async def test_create_child_folder_requires_editor_access(seeded_db):
    bob = await seeded_db.get(User, 2)
    parent = await create_folder_record(seeded_db, owner_id=1)

    seeded_db.add(
        Permission(
            user_id=bob.id,
            resource_type="folder",
            resource_id=parent.id,
            role="viewer",
        )
    )
    await seeded_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await folder_service.create_folder(
            db=seeded_db,
            current_user=bob,
            payload=FolderCreate(name="child", parent_id=parent.id),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "No access to parent folder"


@pytest.mark.asyncio
async def test_delete_folder_soft_deletes_direct_children_and_files(seeded_db):
    alice = await seeded_db.get(User, 1)
    parent = await create_folder_record(seeded_db, owner_id=alice.id)
    child = await create_folder_record(
        seeded_db,
        owner_id=alice.id,
        name="child",
        parent_id=parent.id,
    )
    db_file = await create_file_record(
        seeded_db,
        owner_id=alice.id,
        folder_id=parent.id,
        storage_key="unused.txt",
    )

    await folder_service.delete_folder(seeded_db, alice, parent.id)

    await seeded_db.refresh(parent)
    await seeded_db.refresh(child)
    await seeded_db.refresh(db_file)

    assert parent.deleted_at is not None
    assert child.deleted_at is not None
    assert db_file.deleted_at is not None


@pytest.mark.asyncio
async def test_share_resource_updates_existing_permission(seeded_db):
    alice = await seeded_db.get(User, 1)
    folder = await create_folder_record(seeded_db, owner_id=alice.id)

    viewer_permission = await permission_service.share_resource(
        db=seeded_db,
        current_user=alice,
        resource_type="folder",
        resource_id=folder.id,
        payload=ShareCreate(user_id=2, role="viewer"),
    )

    editor_permission = await permission_service.share_resource(
        db=seeded_db,
        current_user=alice,
        resource_type="folder",
        resource_id=folder.id,
        payload=ShareCreate(user_id=2, role="editor"),
    )

    assert editor_permission.id == viewer_permission.id
    assert editor_permission.role == "editor"


@pytest.mark.asyncio
async def test_share_resource_rejects_invalid_requests(seeded_db):
    alice = await seeded_db.get(User, 1)
    folder = await create_folder_record(seeded_db, owner_id=alice.id)

    cases = [
        ("drive", folder.id, ShareCreate(user_id=2, role="viewer"), 400),
        ("folder", folder.id, ShareCreate(user_id=2, role="admin"), 400),
        ("folder", folder.id, ShareCreate(user_id=999, role="viewer"), 404),
        ("folder", folder.id, ShareCreate(user_id=alice.id, role="viewer"), 400),
    ]

    for resource_type, resource_id, payload, status_code in cases:
        with pytest.raises(HTTPException) as exc_info:
            await permission_service.share_resource(
                db=seeded_db,
                current_user=alice,
                resource_type=resource_type,
                resource_id=resource_id,
                payload=payload,
            )

        assert exc_info.value.status_code == status_code


@pytest.mark.asyncio
async def test_list_and_remove_permissions_enforce_editor_access(seeded_db):
    alice = await seeded_db.get(User, 1)
    bob = await seeded_db.get(User, 2)
    folder = await create_folder_record(seeded_db, owner_id=alice.id)
    permission = await permission_service.share_resource(
        db=seeded_db,
        current_user=alice,
        resource_type="folder",
        resource_id=folder.id,
        payload=ShareCreate(user_id=bob.id, role="viewer"),
    )

    with pytest.raises(HTTPException) as invalid_type:
        await permission_service.list_permissions(seeded_db, alice, "drive", folder.id)
    assert invalid_type.value.status_code == 400

    with pytest.raises(HTTPException) as list_denied:
        await permission_service.list_permissions(seeded_db, bob, "folder", folder.id)
    assert list_denied.value.status_code == 403

    with pytest.raises(HTTPException) as remove_denied:
        await permission_service.remove_permission(seeded_db, bob, permission.id)
    assert remove_denied.value.status_code == 403

    permissions = await permission_service.list_permissions(
        seeded_db,
        alice,
        "folder",
        folder.id,
    )
    assert [item.id for item in permissions] == [permission.id]

    await permission_service.remove_permission(seeded_db, alice, permission.id)
    assert await seeded_db.get(Permission, permission.id) is None

    with pytest.raises(HTTPException) as missing_permission:
        await permission_service.remove_permission(seeded_db, alice, permission.id)
    assert missing_permission.value.status_code == 404


@pytest.mark.asyncio
async def test_file_service_denies_missing_storage_and_unauthorized_upload(
    seeded_db,
    tmp_path,
):
    alice = await seeded_db.get(User, 1)
    bob = await seeded_db.get(User, 2)
    folder = await create_folder_record(seeded_db, owner_id=alice.id)
    missing_path = tmp_path / "missing.txt"
    db_file = await create_file_record(
        seeded_db,
        owner_id=alice.id,
        folder_id=folder.id,
        storage_key=str(missing_path),
    )

    with pytest.raises(HTTPException) as missing_file:
        await file_service.get_file_for_download(seeded_db, alice, db_file.id)
    assert missing_file.value.status_code == 404
    assert missing_file.value.detail == "Stored file missing"

    with pytest.raises(HTTPException) as denied_upload:
        await file_service.upload_file(
            db=seeded_db,
            current_user=bob,
            folder_id=folder.id,
            upload=None,
        )
    assert denied_upload.value.status_code == 403


def test_decode_access_token_rejects_missing_or_invalid_subject():
    missing_subject = jwt.encode(
        {"exp": 4_102_444_800},
        security.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )
    non_integer_subject = jwt.encode(
        {"sub": "not-an-int", "exp": 4_102_444_800},
        security.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )

    for token in [missing_subject, non_integer_subject, "not-a-token"]:
        with pytest.raises(ValueError, match="Invalid token"):
            security.decode_access_token(token)


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token_and_missing_user(seeded_db):
    with pytest.raises(HTTPException) as invalid_token:
        await get_current_user(token="not-a-token", db=seeded_db)
    assert invalid_token.value.status_code == 401
    assert invalid_token.value.detail == "Invalid token"

    missing_user_token = security.create_access_token("999")

    with pytest.raises(HTTPException) as missing_user:
        await get_current_user(token=missing_user_token, db=seeded_db)
    assert missing_user.value.status_code == 401
    assert missing_user.value.detail == "User not found"
