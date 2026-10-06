from __future__ import annotations

import shlex
from types import ModuleType

from api_server.app.remote.engines import comfyui, llama_cpp

ENGINES: dict[str, ModuleType] = {"llama.cpp": llama_cpp, "comfyui": comfyui}
DEFAULT_ENGINE = "llama.cpp"


def get_engine(name: str) -> ModuleType:
    try:
        return ENGINES[name]
    except KeyError as exc:
        supported = ", ".join(ENGINES)
        raise ValueError(f"Unsupported engine: {name}. Supported engines: {supported}") from exc


def quote_path(path: str) -> str:
    """Quote a path for the remote shell while keeping a leading ~ expandable."""
    if path == "~":
        return "~"
    if path.startswith("~/"):
        return "~/" + shlex.quote(path[2:])
    return shlex.quote(path)


def join_argv(argv: list[str]) -> str:
    """Quote a command for the remote shell; only the executable may start with ~."""
    return " ".join([quote_path(argv[0]), *(shlex.quote(arg) for arg in argv[1:])])


def command_line(argv: list[str], env: dict[str, str], cwd: str | None = None) -> str:
    assignments = [f"{key}={shlex.quote(value)}" for key, value in env.items()]
    command = " ".join([*assignments, join_argv(argv)])
    return f"cd {quote_path(cwd)} && {command}" if cwd else command
