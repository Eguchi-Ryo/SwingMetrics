import os
from functools import lru_cache

from sqlalchemy import JSON, Integer, String, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class BenchmarkModel(Base):
    __tablename__ = "benchmark_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)


def build_database_url():
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        return configured_url

    url = URL.create(
        drivername="mysql+pymysql",
        username=os.getenv("MYSQL_USER", "swingmetrics"),
        password=os.getenv("MYSQL_PASSWORD", "swingmetrics_dev_password"),
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.getenv("MYSQL_DATABASE", "swingmetrics"),
        query={"charset": "utf8mb4"},
    )
    return url.render_as_string(hide_password=False)


def payload_belongs_to_owner(payload, owner_key):
    if not owner_key:
        return False
    if payload.get("owner_key") == owner_key:
        return True
    # Preserve access to records written before guest owner keys were introduced.
    if owner_key.startswith("user:"):
        try:
            return payload.get("owner_id") == int(owner_key.partition(":")[2])
        except ValueError:
            return False
    return False


@lru_cache(maxsize=8)
def _engine_for_url(database_url):
    engine_options = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            engine_options["poolclass"] = StaticPool
    return create_engine(database_url, **engine_options)


def get_session_factory(database_url=None):
    database_url = database_url or build_database_url()
    return sessionmaker(bind=_engine_for_url(database_url), expire_on_commit=False)


def initialize_database(database_url=None):
    engine = _engine_for_url(database_url or build_database_url())
    Base.metadata.create_all(engine)


def dispose_database(database_url=None):
    """Dispose a cached connection pool, primarily for isolated tests."""
    database_url = database_url or build_database_url()
    engine = _engine_for_url(database_url)
    engine.dispose()
    _engine_for_url.cache_clear()
