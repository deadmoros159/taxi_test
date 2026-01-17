"""change_telegram_user_id_to_bigint

Revision ID: 003_change_telegram_user_id_to_bigint
Revises: 002_add_telegram_fields
Create Date: 2026-01-17 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_change_telegram_user_id_to_bigint'
down_revision = '002_add_telegram_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Изменяем тип telegram_user_id с INTEGER на BIGINT
    # Telegram user ID может быть больше int32 (2147483647)
    op.alter_column('users', 'telegram_user_id',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)


def downgrade() -> None:
    # Откат: возвращаем INTEGER (может вызвать ошибку если есть большие значения)
    op.alter_column('users', 'telegram_user_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)

