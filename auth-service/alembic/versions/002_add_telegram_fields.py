"""add_telegram_fields

Revision ID: 002_add_telegram_fields
Revises: 001_add_user_role
Create Date: 2026-01-17 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '002_add_telegram_fields'
down_revision = '001_add_user_role'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Проверка существования колонки в таблице"""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(table_name: str, index_name: str) -> bool:
    """Проверка существования индекса"""
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    # Добавляем поля для Telegram
    # Используем BigInteger для telegram_user_id, так как Telegram ID может быть больше int32
    # Проверяем существование колонок перед добавлением (на случай если они были созданы через create_all)
    if not column_exists('users', 'telegram_user_id'):
        op.add_column('users', sa.Column('telegram_user_id', sa.BigInteger(), nullable=True))
    
    if not column_exists('users', 'telegram_username'):
        op.add_column('users', sa.Column('telegram_username', sa.String(), nullable=True))
    
    # Создаем индекс для telegram_user_id (уникальный), если его еще нет
    if not index_exists('users', 'ix_users_telegram_user_id'):
        op.create_index('ix_users_telegram_user_id', 'users', ['telegram_user_id'], unique=True)


def downgrade() -> None:
    # Удаляем индекс, если он существует
    if index_exists('users', 'ix_users_telegram_user_id'):
        op.drop_index('ix_users_telegram_user_id', table_name='users')
    
    # Удаляем колонки, если они существуют
    if column_exists('users', 'telegram_username'):
        op.drop_column('users', 'telegram_username')
    if column_exists('users', 'telegram_user_id'):
        op.drop_column('users', 'telegram_user_id')

