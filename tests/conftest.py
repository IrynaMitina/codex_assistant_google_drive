import os
import shutil
import tempfile
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.models import Base
from app.models.user import User
from app.db.session import get_db
from app.core.security import get_password_hash
from app.core.config import get_settings

settings = get_settings() 
TEST_DB_URL = settings.database_url


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    if os.path.exists("test_drive.db"):
        os.remove("test_drive.db")


@pytest_asyncio.fixture
async def db_session(test_engine):
    TestingSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_db(db_session):
    users = [
        User(
            id=1,
            email="alice@example.com",
            name="Alice",
            password_hash=get_password_hash("alice123"),
        ),
        User(
            id=2,
            email="bob@example.com",
            name="Bob",
            password_hash=get_password_hash("bob123"),
        ),
    ]

    db_session.add_all(users)
    await db_session.commit()

    return db_session


@pytest_asyncio.fixture
async def client(test_engine, seeded_db):
    TestingSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def temp_storage(monkeypatch):
    temp_dir = tempfile.mkdtemp()

    import app.services.storage as storage
    import app.services.files as files

    monkeypatch.setattr(storage, "STORAGE_DIR", temp_dir)
    monkeypatch.setattr(files, "STORAGE_DIR", temp_dir)

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)
