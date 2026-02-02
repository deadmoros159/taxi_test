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
    
    # Проверяем, существует ли таблица orders
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'orders') THEN
                -- Создаем таблицу orders только если её нет
                CREATE TABLE orders (
                    id SERIAL NOT NULL,
                    passenger_id INTEGER NOT NULL,
                    driver_id INTEGER,
                    start_latitude FLOAT NOT NULL,
                    start_longitude FLOAT NOT NULL,
                    start_address VARCHAR NOT NULL,
                    end_latitude FLOAT,
                    end_longitude FLOAT,
                    end_address VARCHAR,
                    status orderstatus NOT NULL DEFAULT 'pending',
                    price FLOAT,
                    estimated_time_minutes INTEGER,
                    driver_location_lat FLOAT,
                    driver_location_lng FLOAT,
                    vehicle_info VARCHAR,
                    cancellation_reason TEXT,
                    cancelled_by INTEGER,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ,
                    accepted_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    cancelled_at TIMESTAMPTZ,
                    PRIMARY KEY (id)
                );
                CREATE INDEX ix_orders_id ON orders (id);
                CREATE INDEX ix_orders_passenger_id ON orders (passenger_id);
                CREATE INDEX ix_orders_driver_id ON orders (driver_id);
                CREATE INDEX ix_orders_status ON orders (status);
            END IF;
        END $$;
    """)
    
    # Проверяем, существует ли таблица driver_debts
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'driver_debts') THEN
                -- Создаем таблицу driver_debts только если её нет
                CREATE TABLE driver_debts (
                    id SERIAL NOT NULL,
                    order_id INTEGER NOT NULL,
                    driver_id INTEGER NOT NULL,
                    amount FLOAT NOT NULL,
                    paid_amount FLOAT NOT NULL DEFAULT 0,
                    remaining_amount FLOAT NOT NULL,
                    is_paid BOOLEAN NOT NULL DEFAULT false,
                    is_blocked BOOLEAN NOT NULL DEFAULT false,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    due_date TIMESTAMPTZ NOT NULL,
                    paid_at TIMESTAMPTZ,
                    blocked_at TIMESTAMPTZ,
                    notes TEXT,
                    PRIMARY KEY (id),
                    FOREIGN KEY (order_id) REFERENCES orders (id)
                );
                CREATE INDEX ix_driver_debts_id ON driver_debts (id);
                CREATE INDEX ix_driver_debts_order_id ON driver_debts (order_id);
                CREATE INDEX ix_driver_debts_driver_id ON driver_debts (driver_id);
                CREATE INDEX ix_driver_debts_is_paid ON driver_debts (is_paid);
                CREATE INDEX ix_driver_debts_is_blocked ON driver_debts (is_blocked);
            END IF;
        END $$;
    """)


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

