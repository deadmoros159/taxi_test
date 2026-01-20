"""add_password_hash

Revision ID: 003_add_password_hash
Revises: 002_add_telegram_fields
Create Date: 2026-01-20 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "003_add_password_hash"
down_revision = "002_add_telegram_fields"
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Nullable for backward compatibility (existing users via phone/telegram/email-code)
    if not column_exists("users", "password_hash"):
        op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))


def downgrade() -> None:
    if column_exists("users", "password_hash"):
        op.drop_column("users", "password_hash")


