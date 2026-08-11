from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine import URL

from config.settings import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)


def build_database_url() -> URL:
    """Build PostgreSQL connection URL safely."""

    return URL.create(
        drivername="postgresql+psycopg2",
        username=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
    )


def get_engine() -> Engine:
    """Create SQLAlchemy database engine."""

    return create_engine(
        build_database_url(),
        pool_pre_ping=True,
        future=True,
    )


def test_connection() -> dict:
    """Test PostgreSQL connectivity."""

    engine = get_engine()

    with engine.connect() as connection:
        result = connection.execute(
            text(
                """
                SELECT
                    current_database() AS database_name,
                    current_user AS database_user,
                    version() AS postgres_version
                """
            )
        ).mappings().one()

    return dict(result)


if __name__ == "__main__":
    result = test_connection()

    print("POSTGRESQL CONNECTION TEST")
    print("--------------------------")
    print("Database:", result["database_name"])
    print("User:", result["database_user"])
    print("Version:", result["postgres_version"])
