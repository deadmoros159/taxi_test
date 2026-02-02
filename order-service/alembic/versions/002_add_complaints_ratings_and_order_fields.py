"""add_complaints_ratings_and_order_fields

Revision ID: 002_add_complaints_ratings_and_order_fields
Revises: 001_initial_orders
Create Date: 2025-02-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '002_add_complaints_ratings_and_order_fields'
down_revision = '001_initial_orders'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем новые поля в таблицу orders
    op.add_column('orders', sa.Column('actual_distance_km', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('actual_time_minutes', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('route_history', sa.Text(), nullable=True))
    
    # Создаем enum для типов жалоб
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE complainttype AS ENUM ('driver_behavior', 'route_issue', 'payment_issue', 'other');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Создаем enum для статусов жалоб
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE complaintstatus AS ENUM ('pending', 'reviewed', 'resolved', 'rejected');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Создаем таблицу complaints
    op.create_table(
        'complaints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('complained_by', sa.Integer(), nullable=False),
        sa.Column('complaint_type', postgresql.ENUM('driver_behavior', 'route_issue', 'payment_issue', 'other', name='complainttype'), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('media_ids', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'reviewed', 'resolved', 'rejected', name='complaintstatus'), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_complaints_id', 'complaints', ['id'], unique=False)
    op.create_index('ix_complaints_order_id', 'complaints', ['order_id'], unique=False)
    op.create_index('ix_complaints_complained_by', 'complaints', ['complained_by'], unique=False)
    op.create_index('ix_complaints_status', 'complaints', ['status'], unique=False)
    
    # Создаем таблицу ratings (только пассажиры оценивают водителей)
    op.create_table(
        'ratings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('passenger_id', sa.Integer(), nullable=False),  # Кто оценил (пассажир)
        sa.Column('driver_id', sa.Integer(), nullable=False),  # Кого оценили (водитель)
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id')
    )
    
    op.create_index('ix_ratings_id', 'ratings', ['id'], unique=False)
    op.create_index('ix_ratings_order_id', 'ratings', ['order_id'], unique=False)
    op.create_index('ix_ratings_passenger_id', 'ratings', ['passenger_id'], unique=False)
    op.create_index('ix_ratings_driver_id', 'ratings', ['driver_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ratings_rated_user_id', table_name='ratings')
    op.drop_index('ix_ratings_rated_by', table_name='ratings')
    op.drop_index('ix_ratings_order_id', table_name='ratings')
    op.drop_index('ix_ratings_id', table_name='ratings')
    op.drop_table('ratings')
    
    op.drop_index('ix_complaints_status', table_name='complaints')
    op.drop_index('ix_complaints_complained_by', table_name='complaints')
    op.drop_index('ix_complaints_order_id', table_name='complaints')
    op.drop_index('ix_complaints_id', table_name='complaints')
    op.drop_table('complaints')
    
    op.execute("DROP TYPE complaintstatus")
    op.execute("DROP TYPE complainttype")
    
    op.drop_column('orders', 'route_history')
    op.drop_column('orders', 'actual_time_minutes')
    op.drop_column('orders', 'actual_distance_km')

