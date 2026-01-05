from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Disable interpolation in ConfigParser to avoid issues with % in URLs
import configparser
config.file_config.parser_class = configparser.RawConfigParser

# Override sqlalchemy.url with DATABASE_URL from environment if available
database_url = os.getenv("DATABASE_URL")
if not database_url:
    # Build DATABASE_URL from individual components if not set
    postgres_user = os.getenv("POSTGRES_USER", "postgres")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "postgres")
    postgres_server = os.getenv("POSTGRES_SERVER", "localhost")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")
    postgres_db = os.getenv("POSTGRES_DB", "auth_db")
    
    # URL encode password if it contains special characters
    from urllib.parse import quote_plus
    encoded_password = quote_plus(postgres_password)
    
    database_url = f"postgresql://{postgres_user}:{encoded_password}@{postgres_server}:{postgres_port}/{postgres_db}"

if database_url:
    # Convert asyncpg URL to psycopg2 for alembic
    if "asyncpg" in database_url:
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    # Use attribute assignment instead of set_main_option to avoid interpolation issues
    config.attributes["sqlalchemy.url"] = database_url

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from app.core.database import Base

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Get URL from attributes first, then from config
    database_url = config.attributes.get("sqlalchemy.url")
    if database_url:
        # Create engine directly from URL to avoid ConfigParser interpolation issues
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

