from __future__ import annotations

import re
import shlex
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from api_server.app.remote.engines import DEFAULT_ENGINE, get_engine

ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Host = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]

RunState = Literal["stopped", "starting", "ready", "running", "exited", "unknown"]
ImportConflict = Literal["skip", "rename", "overwrite"]

EXPORT_FORMAT = "llm-cp-profiles"
EXPORT_VERSION = 1


def _validate_engine(value: str) -> str:
    get_engine(value)
    return value


def _validate_extra_args(value: list[str]) -> list[str]:
    for line in value:
        try:
            shlex.split(line.rstrip().removesuffix("\\"))
        except ValueError as exc:
            raise ValueError(f"Cannot parse extra argument line {line!r}: {exc}") from exc
    return value


def _validate_env(value: dict[str, str]) -> dict[str, str]:
    for key in value:
        if not ENV_KEY.match(key):
            raise ValueError(f"Invalid environment variable name: {key!r}")
    return value


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


class ProfileBase(BaseModel):
    name: Name
    engine: str = Field(default=DEFAULT_ENGINE, max_length=32)
    executable_path: RequiredText
    working_dir: str | None = None
    model_path: str | None = None
    alias: str | None = Field(default=None, max_length=255)
    host: Host = "0.0.0.0"
    port: int = Field(default=8080, ge=1, le=65535)
    ctx_size: int | None = Field(default=None, ge=0)
    n_gpu_layers: int | None = Field(default=None, ge=-1)
    engine_options: dict[str, Any] = Field(default_factory=dict)
    extra_args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    notes: str = ""

    _engine = field_validator("engine")(_validate_engine)
    _extra_args = field_validator("extra_args")(_validate_extra_args)
    _env = field_validator("env")(_validate_env)
    _blank = field_validator("working_dir", "model_path", "alias")(_blank_to_none)


class ProfileCreate(ProfileBase):
    @model_validator(mode="after")
    def validate_for_engine(self) -> Self:
        get_engine(self.engine).validate(self)
        return self


class ProfileUpdate(BaseModel):
    name: Name | None = None
    engine: str | None = Field(default=None, max_length=32)
    executable_path: RequiredText | None = None
    working_dir: str | None = None
    model_path: str | None = None
    alias: str | None = Field(default=None, max_length=255)
    host: Host | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    ctx_size: int | None = Field(default=None, ge=0)
    n_gpu_layers: int | None = Field(default=None, ge=-1)
    engine_options: dict[str, Any] | None = None
    extra_args: list[str] | None = None
    env: dict[str, str] | None = None
    notes: str | None = None

    _blank = field_validator("working_dir", "model_path", "alias")(_blank_to_none)

    @field_validator("engine")
    @classmethod
    def validate_engine(cls, value: str | None) -> str | None:
        return None if value is None else _validate_engine(value)

    @field_validator("extra_args")
    @classmethod
    def validate_extra_args(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _validate_extra_args(value)

    @field_validator("env")
    @classmethod
    def validate_env(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        return None if value is None else _validate_env(value)


class RunStatus(BaseModel):
    status: RunState = "stopped"
    pid: int | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    # True when the profile was edited after the running process was launched.
    command_changed: bool = False


class ProfileRead(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    command: str
    run: RunStatus
    created_at: datetime
    updated_at: datetime


class ProfileOrder(BaseModel):
    ids: list[str]


class ProfileExport(BaseModel):
    format: Literal["llm-cp-profiles"]
    version: Literal[1]
    exported_at: datetime | None = None
    profiles: list[ProfileCreate]


class ImportResult(BaseModel):
    created: list[str]
    updated: list[str]
    skipped: list[str]


class CommandPreview(BaseModel):
    command: str
    argv: list[str]
