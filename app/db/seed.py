# app/db/seed.py
import asyncio

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def seed_users() -> None:
    async with AsyncSessionLocal() as db:
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

        for user in users:
            existing = await db.get(User, user.id)
            if not existing:
                db.add(user)

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed_users())