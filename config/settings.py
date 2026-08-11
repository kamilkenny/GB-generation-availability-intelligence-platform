from pathlib import Path
import os

from dotenv import load_dotenv


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

RAW_DATA_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
LOG_DIR = BASE_DIR / "logs"


# ---------------------------------------------------------
# External services
# ---------------------------------------------------------

DEFAULT_ELEXON_BASE_URL = (
    "https://" + "data.elexon.co.uk" + "/bmrs/api/v1"
)

ELEXON_BASE_URL = os.getenv(
    "ELEXON_BASE_URL",
    DEFAULT_ELEXON_BASE_URL,
)


# ---------------------------------------------------------
# Application environment
# ---------------------------------------------------------

APP_ENV = os.getenv("APP_ENV", "development")


# ---------------------------------------------------------
# Ensure required directories exist
# ---------------------------------------------------------

RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
