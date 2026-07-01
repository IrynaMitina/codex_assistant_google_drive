import pytest


async def get_token(client, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": email,
            "password": password,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_folder(client):
    token = await get_token(client, "alice@example.com", "alice123")

    response = await client.post(
        "/api/v1/drive/folders",
        json={"name": "docs", "parent_id": None},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "docs"
    assert data["parent_id"] is None


@pytest.mark.asyncio
async def test_upload_and_list_file(client, temp_storage):
    token = await get_token(client, "alice@example.com", "alice123")

    folder_response = await client.post(
        "/api/v1/drive/folders",
        json={"name": "docs", "parent_id": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    folder_id = folder_response.json()["id"]

    upload_response = await client.post(
        f"/api/v1/drive/folders/{folder_id}/files",
        files={"upload": ("a.txt", b"hello world", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert upload_response.status_code == 201

    file_data = upload_response.json()
    assert file_data["name"] == "a.txt"
    assert file_data["mime_type"] == "text/plain"
    assert file_data["size_bytes"] == 11

    list_response = await client.get(
        f"/api/v1/drive/folders/{folder_id}/contents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert list_response.status_code == 200

    contents = list_response.json()
    assert contents["folders"] == []
    assert len(contents["files"]) == 1
    assert contents["files"][0]["name"] == "a.txt"


@pytest.mark.asyncio
async def test_share_file_and_download_by_another_user(client, temp_storage):
    alice_token = await get_token(client, "alice@example.com", "alice123")
    bob_token = await get_token(client, "bob@example.com", "bob123")

    folder_response = await client.post(
        "/api/v1/drive/folders",
        json={"name": "docs", "parent_id": None},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    folder_id = folder_response.json()["id"]

    upload_response = await client.post(
        f"/api/v1/drive/folders/{folder_id}/files",
        files={"upload": ("a.txt", b"shared file", "text/plain")},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    file_id = upload_response.json()["id"]

    denied_response = await client.get(
        f"/api/v1/drive/files/{file_id}/download",
        headers={"Authorization": f"Bearer {bob_token}"},
    )

    assert denied_response.status_code == 403

    share_response = await client.post(
        f"/api/v1/drive/file/{file_id}/share",
        json={"user_id": 2, "role": "viewer"},
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert share_response.status_code == 201

    download_response = await client.get(
        f"/api/v1/drive/files/{file_id}/download",
        headers={"Authorization": f"Bearer {bob_token}"},
    )

    assert download_response.status_code == 200
    assert download_response.content == b"shared file"


@pytest.mark.asyncio
async def test_owner_can_create_public_shared_link_and_anyone_can_download(client, temp_storage):
    alice_token = await get_token(client, "alice@example.com", "alice123")

    folder_response = await client.post(
        "/api/v1/drive/folders",
        json={"name": "public-docs", "parent_id": None},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    folder_id = folder_response.json()["id"]

    upload_response = await client.post(
        f"/api/v1/drive/folders/{folder_id}/files",
        files={"upload": ("public.txt", b"public file", "text/plain")},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    file_id = upload_response.json()["id"]

    share_response = await client.post(
        f"/api/v1/drive/files/{file_id}/shared-link",
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert share_response.status_code == 200
    share_data = share_response.json()
    assert share_data["token"]
    assert share_data["url_path"].endswith(f"/shared-links/{share_data['token']}/download")

    download_response = await client.get(share_data["url_path"])

    assert download_response.status_code == 200
    assert download_response.content == b"public file"


@pytest.mark.asyncio
async def test_shared_link_can_only_be_created_by_owner(client, temp_storage):
    alice_token = await get_token(client, "alice@example.com", "alice123")
    bob_token = await get_token(client, "bob@example.com", "bob123")

    folder_response = await client.post(
        "/api/v1/drive/folders",
        json={"name": "private-docs", "parent_id": None},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    folder_id = folder_response.json()["id"]

    upload_response = await client.post(
        f"/api/v1/drive/folders/{folder_id}/files",
        files={"upload": ("private.txt", b"private file", "text/plain")},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    file_id = upload_response.json()["id"]

    share_response = await client.post(
        f"/api/v1/drive/files/{file_id}/shared-link",
        headers={"Authorization": f"Bearer {bob_token}"},
    )

    assert share_response.status_code == 403


@pytest.mark.asyncio
async def test_shared_link_is_reused_and_can_be_revoked(client, temp_storage):
    alice_token = await get_token(client, "alice@example.com", "alice123")

    folder_response = await client.post(
        "/api/v1/drive/folders",
        json={"name": "revoked-docs", "parent_id": None},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    folder_id = folder_response.json()["id"]

    upload_response = await client.post(
        f"/api/v1/drive/folders/{folder_id}/files",
        files={"upload": ("revoked.txt", b"revoked file", "text/plain")},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    file_id = upload_response.json()["id"]

    first_share_response = await client.post(
        f"/api/v1/drive/files/{file_id}/shared-link",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    second_share_response = await client.post(
        f"/api/v1/drive/files/{file_id}/shared-link",
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert first_share_response.status_code == 200
    assert second_share_response.status_code == 200
    assert first_share_response.json()["token"] == second_share_response.json()["token"]

    url_path = first_share_response.json()["url_path"]

    revoke_response = await client.delete(
        f"/api/v1/drive/files/{file_id}/shared-link",
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert revoke_response.status_code == 204

    download_response = await client.get(url_path)

    assert download_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_file(client, temp_storage):
    token = await get_token(client, "alice@example.com", "alice123")

    folder_response = await client.post(
        "/api/v1/drive/folders",
        json={"name": "docs", "parent_id": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    folder_id = folder_response.json()["id"]

    upload_response = await client.post(
        f"/api/v1/drive/folders/{folder_id}/files",
        files={"upload": ("a.txt", b"to delete", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    file_id = upload_response.json()["id"]

    delete_response = await client.delete(
        f"/api/v1/drive/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert delete_response.status_code == 204

    download_response = await client.get(
        f"/api/v1/drive/files/{file_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert download_response.status_code == 403 or download_response.status_code == 404
