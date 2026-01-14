from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context
import configparser

config = context.config
config.file_config.parser_class = configparser.RawConfigParser

# Override sqlalchemy.url with DATABASE_URL from environment if available
database_url = os.getenv("DATABASE_URL")
if not database_url:
    postgres_user = os.getenv("POSTGRES_USER", "postgres")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "postgres")
    postgres_server = os.getenv("POSTGRES_SERVER", "localhost")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")
    postgres_db = os.getenv("POSTGRES_DB", "order_db")
    
    from urllib.parse import quote_plus
    encoded_password = quote_plus(postgres_password)
    database_url = f"postgresql://{postgres_user}:{encoded_password}@{postgres_server}:{postgres_port}/{postgres_db}"

if database_url:
    if "asyncpg" in database_url:
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    config.attributes["sqlalchemy.url"] = database_url

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.core.database import Base
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.attributes.get("sqlalchemy.url") or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database_url = config.attributes.get("sqlalchemy.url")
    if database_url:
        from sqlalchemy import create_engine
        connectable = create_engine(database_url, poolclass=pool.NullPool)
    else:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


