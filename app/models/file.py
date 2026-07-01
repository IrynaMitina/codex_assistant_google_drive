from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    folder_id: Mapped[int] = mapped_column(
        ForeignKey("folders.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)  # key to store file in storage backend (e.g. S3)
    checksum: Mapped[str | None] = mapped_column(String(128))  # fingerprint for verification & deduplication
    shared_link_token: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # soft delete

    owner: Mapped["User"] = relationship(back_populates="files")
    folder: Mapped["Folder"] = relationship(back_populates="files")

    __table_args__ = (
        UniqueConstraint("folder_id", "name", name="uq_file_name_per_folder"),
        Index("ix_files_owner_folder", "owner_id", "folder_id"),
    )
