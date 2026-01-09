"""initial_orders

Revision ID: 001_initial_orders
Revises: 
Create Date: 2024-12-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '001_initial_orders'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создаем enum для статусов заказов (если еще не существует)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE orderstatus AS ENUM ('pending', 'accepted', 'driver_arrived', 'in_progress', 'completed', 'cancelled', 'cancelled_by_driver', 'cancelled_by_passenger');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Создаем таблицу orders
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('passenger_id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=True),
        sa.Column('start_latitude', sa.Float(), nullable=False),
        sa.Column('start_longitude', sa.Float(), nullable=False),
        sa.Column('start_address', sa.String(), nullable=False),
        sa.Column('end_latitude', sa.Float(), nullable=True),
        sa.Column('end_longitude', sa.Float(), nullable=True),
        sa.Column('end_address', sa.String(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'accepted', 'driver_arrived', 'in_progress', 'completed', 'cancelled', 'cancelled_by_driver', 'cancelled_by_passenger', name='orderstatus'), nullable=False),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('estimated_time_minutes', sa.Integer(), nullable=True),
        sa.Column('driver_location_lat', sa.Float(), nullable=True),
        sa.Column('driver_location_lng', sa.Float(), nullable=True),
        sa.Column('vehicle_info', sa.String(), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('cancelled_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_orders_id', 'orders', ['id'], unique=False)
    op.create_index('ix_orders_passenger_id', 'orders', ['passenger_id'], unique=False)
    op.create_index('ix_orders_driver_id', 'orders', ['driver_id'], unique=False)
    op.create_index('ix_orders_status', 'orders', ['status'], unique=False)
    
    # Создаем таблицу driver_debts
    op.create_table(
        'driver_debts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('paid_amount', sa.Float(), nullable=False, server_default='0'),
        sa.Column('remaining_amount', sa.Float(), nullable=False),
        sa.Column('is_paid', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_blocked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('blocked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_driver_debts_id', 'driver_debts', ['id'], unique=False)
    op.create_index('ix_driver_debts_order_id', 'driver_debts', ['order_id'], unique=False)
    op.create_index('ix_driver_debts_driver_id', 'driver_debts', ['driver_id'], unique=False)
    op.create_index('ix_driver_debts_is_paid', 'driver_debts', ['is_paid'], unique=False)
    op.create_index('ix_driver_debts_is_blocked', 'driver_debts', ['is_blocked'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_driver_debts_is_blocked', table_name='driver_debts')
    op.drop_index('ix_driver_debts_is_paid', table_name='driver_debts')
    op.drop_index('ix_driver_debts_driver_id', table_name='driver_debts')
    op.drop_index('ix_driver_debts_order_id', table_name='driver_debts')
    op.drop_index('ix_driver_debts_id', table_name='driver_debts')
    op.drop_table('driver_debts')
    
    op.drop_index('ix_orders_status', table_name='orders')
    op.drop_index('ix_orders_driver_id', table_name='orders')
    op.drop_index('ix_orders_passenger_id', table_name='orders')
    op.drop_index('ix_orders_id', table_name='orders')
    op.drop_table('orders')
    
    op.execute("DROP TYPE orderstatus")

