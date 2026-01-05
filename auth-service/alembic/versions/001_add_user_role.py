"""add_user_role

Revision ID: 001_add_user_role
Revises: 000_initial_create_tables
Create Date: 2024-12-04 13:51:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_add_user_role'
down_revision = '000_initial_create_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Колонка role уже создана в начальной миграции
    # Эта миграция оставлена для совместимости, но ничего не делает
    # Если нужно изменить что-то в колонке role, это можно сделать здесь
    pass


def downgrade() -> None:
    # Откат не требуется, так как колонка создана в начальной миграции
    pass

