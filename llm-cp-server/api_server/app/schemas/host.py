from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HostRead(BaseModel):
    mode: str
    target: str
    connected: bool
    error: str | None = None
    gpu_error: str | None = None


class DirEntryRead(BaseModel):
    name: str
    is_dir: bool
    size: int | None = None


class DirListingRead(BaseModel):
    path: str
    parent: str | None = None
    entries: list[DirEntryRead]


class GpuRead(BaseModel):
    error: str | None = None
    snapshot: dict[str, Any] | None = None


class SystemRead(BaseModel):
    error: str | None = None
    snapshot: dict[str, Any] | None = None
