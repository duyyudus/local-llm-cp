from __future__ import annotations

import posixpath
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from api_server.app.remote.engines.llama_cpp import LOOPBACK_FOR_WILDCARD, split_extra_args
from api_server.app.remote.executor import RemoteExecutor, bash

LAUNCHER = "start.sh"
BASE_CONFIG = "config.yml"
MAX_CONFIG_BYTES = 1024 * 1024

# Settings the form offers, by the config section and key tabbyAPI keeps them under.
SETTINGS = {
    "host": ("network", "host"),
    "port": ("network", "port"),
    "model_name": ("model", "model_name"),
    "max_seq_len": ("model", "max_seq_len"),
    "gpu_split": ("model", "gpu_split"),
}
# tabbyAPI's own defaults for what no config sets.
DEFAULTS: dict[str, Any] = {"host": "127.0.0.1", "port": 5000}


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: str | None = None
    model_name: str | None = None
    max_seq_len: int | None = Field(default=None, ge=-1)
    gpu_split: list[float] = Field(default_factory=list)

    @field_validator("config", "model_name")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None

    @field_validator("gpu_split")
    @classmethod
    def positive_sizes(cls, value: list[float]) -> list[float]:
        if any(size < 0 for size in value):
            raise ValueError("GPU split sizes must not be negative")
        return value


class ProfileLike(Protocol):
    executable_path: str
    working_dir: str | None
    host: str
    port: int
    engine_options: dict[str, Any]
    extra_args: list[str]
    env: dict[str, str]


class SourceLike(Protocol):
    working_dir: str | None
    engine_options: dict[str, Any]
    env: dict[str, str]


def parse_options(options: dict[str, Any]) -> Options:
    try:
        return Options.model_validate(options)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ValueError(f"Invalid tabbyAPI options: {problems}") from exc


def validate(profile: ProfileLike) -> None:
    if not profile.working_dir:
        raise ValueError("tabbyAPI needs its repository directory as the working directory")
    parse_options(profile.engine_options)


def build_argv(profile: ProfileLike) -> list[str]:
    """`executable_path` is the launcher script, relative to the repository unless absolute.

    Every value set in the profile is passed as a flag, which tabbyAPI lays over the config
    file; what the profile leaves empty comes from the file.
    """
    options = parse_options(profile.engine_options)
    launcher = profile.executable_path
    if profile.working_dir and not launcher.startswith(("/", "~")):
        launcher = posixpath.join(profile.working_dir, launcher)
    argv = [launcher]
    if options.config:
        argv += ["--config", options.config]
    if profile.host:
        argv += ["--host", profile.host]
    argv += ["--port", str(profile.port)]
    if options.model_name:
        argv += ["--model-name", options.model_name]
    if options.max_seq_len is not None:
        argv += ["--max-seq-len", str(options.max_seq_len)]
    if options.gpu_split:
        argv += ["--gpu-split", *(f"{size:g}" for size in options.gpu_split)]
    # Last, so a flag repeated here wins over the form field.
    argv += split_extra_args(profile.extra_args)
    return argv


def working_dir(profile: ProfileLike) -> str | None:
    return profile.working_dir


def health_url(profile: ProfileLike) -> str:
    host = "127.0.0.1" if profile.host in LOOPBACK_FOR_WILDCARD else profile.host
    return f"http://{host}:{profile.port}/health"


def config_settings(text: str) -> dict[str, Any] | None:
    """The form's settings a config file sets; None when the file is not a usable config."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if data is None:
        return {}
    if not isinstance(data, dict):
        return None
    found: dict[str, Any] = {}
    for name, (section, key) in SETTINGS.items():
        values = data.get(section) or {}
        if not isinstance(values, dict):
            return None
        if values.get(key) is not None:
            found[name] = values[key]
    return found


def env_settings(env: dict[str, str]) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for name, (section, key) in SETTINGS.items():
        value = env.get(f"TABBY_{section}_{key}".upper())
        if value is not None:
            found[name] = value
    return found


def clean_settings(values: dict[str, Any]) -> dict[str, Any]:
    """Keep the values that would load, typed the way the form shows them."""
    clean: dict[str, Any] = {}
    for name, value in values.items():
        if isinstance(value, bool):
            continue
        try:
            if name in ("host", "model_name"):
                clean[name] = str(value)
            elif name == "port":
                port = int(str(value).strip())
                if 1 <= port <= 65535:
                    clean[name] = port
            elif name == "max_seq_len":
                clean[name] = int(str(value).strip())
            elif name == "gpu_split" and isinstance(value, list):
                clean[name] = [float(size) for size in value]
        except (TypeError, ValueError):
            continue
    return clean


def merge_settings(layers: list[dict[str, Any]]) -> dict[str, Any]:
    """Later layers win and unset values fall through, as tabbyAPI merges its configs."""
    merged = dict(DEFAULTS)
    for layer in layers:
        merged.update(layer)
    return clean_settings(merged)


async def read_defaults(executor: RemoteExecutor, source: SourceLike) -> dict[str, Any] | None:
    """What the server gets for each form setting the profile leaves empty."""
    # Imported here: the package __init__ imports this module.
    from api_server.app.remote.engines import quote_path

    if not source.working_dir:
        return None
    config = parse_options(source.engine_options).config

    async def read(path: str) -> str | None:
        script = (
            f"cd -- {quote_path(source.working_dir or '.')} && "
            f"head -c {MAX_CONFIG_BYTES} -- {quote_path(path)}"
        )
        result = await executor.run(bash(script))
        return result.stdout if result.ok else None

    # tabbyAPI loads the repository's config.yml first, then TABBY_* variables, then the
    # --config file.
    base_text = await read(BASE_CONFIG)
    base = {} if base_text is None else config_settings(base_text)
    override: dict[str, Any] | None = {}
    if config:
        override_text = await read(config)
        override = None if override_text is None else config_settings(override_text)
    if base is None or override is None:
        return None
    return merge_settings([base, env_settings(source.env), override])
