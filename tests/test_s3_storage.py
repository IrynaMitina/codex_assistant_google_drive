import os
from io import BytesIO

import pytest

from app.services import storage
from app.services.storage import LocalStorageBackend, S3StorageBackend
from tests.test_drive_api import get_token


class FakeS3Client:
    class S3Error(Exception):
        def __init__(self, status_code: int = 404, code: str = "NoSuchKey") -> None:
            self.response = {
                "ResponseMetadata": {"HTTPStatusCode": status_code},
                "Error": {"Code": code},
            }

    def __init__(self) -> None:
        self.objects = {}
        self.deleted = []

    def upload_fileobj(self, file_obj, bucket, key, ExtraArgs=None):
        self.objects[(bucket, key)] = {
            "body": file_obj.read(),
            "content_type": (ExtraArgs or {}).get("ContentType"),
        }

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise self.S3Error()
        return {}

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise self.S3Error()
        return {"Body": BytesIO(self.objects[(Bucket, Key)]["body"])}

    def delete_object(self, Bucket, Key):
        self.deleted.append((Bucket, Key))
        self.objects.pop((Bucket, Key), None)


@pytest.fixture
def fake_s3_backend(monkeypatch):
    backend = S3StorageBackend(
        bucket_name="test-bucket",
        region_name="us-east-1",
        client=FakeS3Client(),
    )

    monkeypatch.setattr(storage, "get_storage_backend", lambda: backend)

    return backend


def test_local_backend_preserves_legacy_storage_dir_keys(tmp_path):
    storage_dir = tmp_path / "storage"
    backend = LocalStorageBackend(str(storage_dir))
    relative_backend = LocalStorageBackend("./storage")

    new_key = "1/new-uuid/a.txt"
    relative_new_path = os.path.join("./storage", new_key)
    relative_legacy_key = os.path.join(str(storage_dir), "1", "old-uuid", "a.txt")
    absolute_legacy_key = os.path.abspath(relative_legacy_key)

    assert backend._path_for_key(new_key) == os.path.join(str(storage_dir), new_key)
    assert backend._path_for_key(relative_legacy_key) == relative_legacy_key
    assert backend._path_for_key(absolute_legacy_key) == absolute_legacy_key
    assert relative_backend._path_for_key(new_key) == relative_new_path
    assert relative_backend._path_for_key(relative_new_path) == relative_new_path
    assert relative_backend._path_for_key(os.path.normpath(relative_new_path)) == os.path.normpath(
        relative_new_path
    )


@pytest.mark.asyncio
async def test_s3_backend_uploads_downloads_and_deletes_through_api(client, fake_s3_backend):
    token = await get_token(client, "alice@example.com", "alice123")

    folder_response = await client.post(
        "/api/v1/drive/folders",
        json={"name": "s3-docs", "parent_id": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    folder_id = folder_response.json()["id"]

    upload_response = await client.post(
        f"/api/v1/drive/folders/{folder_id}/files",
        files={"upload": ("s3.txt", b"hello from s3", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert upload_response.status_code == 201
    file_data = upload_response.json()
    assert file_data["name"] == "s3.txt"
    assert file_data["size_bytes"] == 13
    [(bucket_name, storage_key)] = fake_s3_backend.client.objects.keys()
    assert bucket_name == fake_s3_backend.bucket_name
    assert storage_key.endswith("/s3.txt")

    download_response = await client.get(
        f"/api/v1/drive/files/{file_data['id']}/download",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert download_response.status_code == 200
    assert download_response.content == b"hello from s3"

    delete_response = await client.delete(
        f"/api/v1/drive/files/{file_data['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert delete_response.status_code == 204
    assert (fake_s3_backend.bucket_name, storage_key) in fake_s3_backend.client.deleted


@pytest.mark.asyncio
async def test_s3_backend_reports_missing_objects(fake_s3_backend):
    assert await fake_s3_backend.exists("missing.txt") is False
