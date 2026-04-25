import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


if os.getenv("DATABASE_URL") is None:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql://" + database_url[len("postgres://") :]
    return database_url


def _build_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url is None:
        raise RuntimeError("DATABASE_URL is not set")

    return _normalize_database_url(database_url)


DATABASE_URL = _build_database_url()
_parsed_db_url = urlparse(str(DATABASE_URL))
print(
    f"[DB CONFIG] DATABASE_URL env present={os.getenv('DATABASE_URL') is not None}, "
    f"host={_parsed_db_url.hostname}, db={_parsed_db_url.path.lstrip('/')}"
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_connection():
    return psycopg2.connect(DATABASE_URL)
