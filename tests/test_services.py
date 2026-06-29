import pytest


from app.models.folder import Folder
from app.models.permission import Permission
from app.models.user import User
from app.schemas.drive import FolderCreate, ShareCreate
from app.services import folders as folder_service
from app.services import permissions as permission_service
from app.services.access import has_access


@pytest.mark.asyncio
async def test_create_folder_service(seeded_db):
    user = await seeded_db.get(User, 1)

    folder = await folder_service.create_folder(
        db=seeded_db,
        current_user=user,
        payload=FolderCreate(name="docs", parent_id=None),
    )

    assert folder.id is not None
    assert folder.name == "docs"
    assert folder.owner_id == user.id


@pytest.mark.asyncio
async def test_owner_has_access_to_folder(seeded_db):
    user = await seeded_db.get(User, 1)

    folder = Folder(
        owner_id=user.id,
        parent_id=None,
        name="docs",
    )
    seeded_db.add(folder)
    await seeded_db.commit()
    await seeded_db.refresh(folder)

    assert await has_access(seeded_db, user, "folder", folder.id, "viewer") is True
    assert await has_access(seeded_db, user, "folder", folder.id, "editor") is True


@pytest.mark.asyncio
async def test_shared_viewer_has_viewer_access_only(seeded_db):
    alice = await seeded_db.get(User, 1)
    bob = await seeded_db.get(User, 2)

    folder = Folder(
        owner_id=alice.id,
        parent_id=None,
        name="docs",
    )
    seeded_db.add(folder)
    await seeded_db.commit()
    await seeded_db.refresh(folder)

    permission = Permission(
        user_id=bob.id,
        resource_type="folder",
        resource_id=folder.id,
        role="viewer",
    )
    seeded_db.add(permission)
    await seeded_db.commit()

    assert await has_access(seeded_db, bob, "folder", folder.id, "viewer") is True
    assert await has_access(seeded_db, bob, "folder", folder.id, "editor") is False


@pytest.mark.asyncio
async def test_share_resource_service(seeded_db):
    alice = await seeded_db.get(User, 1)

    folder = Folder(
        owner_id=alice.id,
        parent_id=None,
        name="docs",
    )
    seeded_db.add(folder)
    await seeded_db.commit()
    await seeded_db.refresh(folder)

    permission = await permission_service.share_resource(
        db=seeded_db,
        current_user=alice,
        resource_type="folder",
        resource_id=folder.id,
        payload=ShareCreate(user_id=2, role="viewer"),
    )

    assert permission.id is not None
    assert permission.user_id == 2
    assert permission.resource_type == "folder"
    assert permission.resource_id == folder.id
    assert permission.role == "viewer"
