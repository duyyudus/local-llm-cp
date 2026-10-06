from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class UTCDateTime(TypeDecorator):
    """SQLite drops tzinfo; values are stored as UTC and returned timezone-aware."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("prf"))
    name: Mapped[str] = mapped_column(String(120), unique=True)
    engine: Mapped[str] = mapped_column(String(32), default="llama.cpp")
    executable_path: Mapped[str] = mapped_column(Text)
    working_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    alias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    host: Mapped[str] = mapped_column(String(255), default="0.0.0.0")
    port: Mapped[int] = mapped_column(Integer, default=8080)
    ctx_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    n_gpu_layers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine_options: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    extra_args: Mapped[list[str]] = mapped_column(JSON, default=list)
    env: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("run"))
    profile_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    pid: Mapped[int] = mapped_column(Integer)
    command: Mapped[list[str]] = mapped_column(JSON)
    port: Mapped[int] = mapped_column(Integer)
    health_url: Mapped[str] = mapped_column(Text)
    log_path: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    stopped_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
