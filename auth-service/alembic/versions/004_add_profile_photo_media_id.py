"""add_photo_id

Revision ID: 004_add_photo_id
Revises: 003_add_password_hash
Create Date: 2026-02-02 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "004_add_photo_id"
down_revision = "003_add_password_hash"
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Добавляем поле для ID фото профиля в media-service
    if not column_exists("users", "photo_id"):
        op.add_column(
            "users",
            sa.Column("photo_id", sa.Integer(), nullable=True)
        )
        # Создаем индекс для быстрого поиска
        op.create_index(
            "ix_users_photo_id",
            "users",
            ["photo_id"]
        )


def downgrade() -> None:
    if column_exists("users", "photo_id"):
        # Удаляем индекс
        op.drop_index("ix_users_photo_id", table_name="users")
        # Удаляем колонку
        op.drop_column("users", "photo_id")

