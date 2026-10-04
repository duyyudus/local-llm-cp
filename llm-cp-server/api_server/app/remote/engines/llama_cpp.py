from __future__ import annotations

import posixpath
import shlex
from typing import Protocol

LOOPBACK_FOR_WILDCARD = {"", "0.0.0.0", "::", "[::]", "*"}


class ProfileLike(Protocol):
    executable_path: str
    working_dir: str | None
    model_path: str | None
    alias: str | None
    host: str
    port: int
    ctx_size: int | None
    n_gpu_layers: int | None
    extra_args: list[str]


def split_extra_args(lines: list[str]) -> list[str]:
    """Each entry is one line as it would appear in a shell script, e.g. `--temp 0.7 \\`."""
    tokens: list[str] = []
    for line in lines:
        text = line.strip()
        if text.endswith("\\"):
            text = text[:-1].rstrip()
        if not text or text.startswith("#"):
            continue
        tokens.extend(shlex.split(text))
    return tokens


def build_argv(profile: ProfileLike) -> list[str]:
    argv = [profile.executable_path]
    if profile.model_path:
        argv += ["--model", profile.model_path]
    if profile.alias:
        argv += ["--alias", profile.alias]
    if profile.host:
        argv += ["--host", profile.host]
    argv += ["--port", str(profile.port)]
    if profile.ctx_size is not None:
        argv += ["--ctx-size", str(profile.ctx_size)]
    if profile.n_gpu_layers is not None:
        argv += ["--n-gpu-layers", str(profile.n_gpu_layers)]
    argv += split_extra_args(profile.extra_args)
    return argv


def working_dir(profile: ProfileLike) -> str | None:
    """Relative paths in arguments resolve here; by default next to the executable."""
    if profile.working_dir:
        return profile.working_dir
    if profile.executable_path.startswith(("/", "~")):
        return posixpath.dirname(profile.executable_path)
    return None


def health_url(profile: ProfileLike) -> str:
    host = "127.0.0.1" if profile.host in LOOPBACK_FOR_WILDCARD else profile.host
    return f"http://{host}:{profile.port}/health"
