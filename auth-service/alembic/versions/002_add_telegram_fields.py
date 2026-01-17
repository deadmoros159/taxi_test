"""add_telegram_fields

Revision ID: 002_add_telegram_fields
Revises: 001_add_user_role
Create Date: 2026-01-17 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_telegram_fields'
down_revision = '001_add_user_role'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поля для Telegram
    # Используем BigInteger для telegram_user_id, так как Telegram ID может быть больше int32
    op.add_column('users', sa.Column('telegram_user_id', sa.BigInteger(), nullable=True))
    op.add_column('users', sa.Column('telegram_username', sa.String(), nullable=True))
    
    # Создаем индекс для telegram_user_id (уникальный)
    op.create_index('ix_users_telegram_user_id', 'users', ['telegram_user_id'], unique=True)


def downgrade() -> None:
    # Удаляем индекс
    op.drop_index('ix_users_telegram_user_id', table_name='users')
    
    # Удаляем колонки
    op.drop_column('users', 'telegram_username')
    op.drop_column('users', 'telegram_user_id')

