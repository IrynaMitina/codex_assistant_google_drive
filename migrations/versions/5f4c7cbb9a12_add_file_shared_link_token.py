"""add file shared link token

Revision ID: 5f4c7cbb9a12
Revises: 487512d812fd
Create Date: 2026-07-01 12:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5f4c7cbb9a12"
down_revision: Union[str, Sequence[str], None] = "487512d812fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "files",
        sa.Column("shared_link_token", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_files_shared_link_token"),
        "files",
        ["shared_link_token"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_files_shared_link_token"), table_name="files")
    op.drop_column("files", "shared_link_token")
