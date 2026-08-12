from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# =========================================================
# PROJECT DIRECTORIES
# =========================================================

RAW_DATA_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
LOG_DIR = BASE_DIR / "logs"

# Remote Git job source is read-only in Databricks.
# Local development still creates the project directories.
IS_DATABRICKS_WORKSPACE = str(BASE_DIR).startswith("/Workspace/")

if not IS_DATABRICKS_WORKSPACE:
    RAW_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# =========================================================
# ELEXON
# =========================================================

ELEXON_BASE_URL = os.getenv(
    "ELEXON_BASE_URL",
    "https://data.elexon.co.uk/bmrs/api/v1",
)


# =========================================================
# POSTGRESQL
# =========================================================

POSTGRES_HOST = os.getenv(
    "POSTGRES_HOST",
    "localhost",
)

POSTGRES_PORT = int(
    os.getenv(
        "POSTGRES_PORT",
        "5432",
    )
)

POSTGRES_DB = os.getenv(
    "POSTGRES_DB",
    "gb_energy",
)

POSTGRES_USER = os.getenv(
    "POSTGRES_USER",
    "gb_energy_user",
)

POSTGRES_PASSWORD = os.getenv(
    "POSTGRES_PASSWORD",
    "",
)


# =========================================================
# APPLICATION
# =========================================================

APP_ENV = os.getenv(
    "APP_ENV",
    "development",
)
