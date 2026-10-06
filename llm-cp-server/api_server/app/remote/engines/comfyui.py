from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from api_server.app.remote.engines.llama_cpp import LOOPBACK_FOR_WILDCARD, split_extra_args

ENTRY_POINT = "main.py"

# Option name to the flag it switches on, in the order they appear on the command line.
SWITCHES = {
    "fast": "--fast",
    "disable_smart_memory": "--disable-smart-memory",
    "enable_cors_header": "--enable-cors-header",
    "multi_user": "--multi-user",
    "disable_all_custom_nodes": "--disable-all-custom-nodes",
    "enable_manager": "--enable-manager",
}
VALUES = {
    "preview_method": "--preview-method",
    "reserve_vram": "--reserve-vram",
    "output_directory": "--output-directory",
    "input_directory": "--input-directory",
    "extra_model_paths_config": "--extra-model-paths-config",
}


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vram_mode: Literal["gpu-only", "highvram", "normalvram", "lowvram", "novram", "cpu"] | None = (
        None
    )
    preview_method: Literal["none", "auto", "latent2rgb", "taesd"] | None = None
    reserve_vram: float | None = Field(default=None, ge=0)
    output_directory: str | None = None
    input_directory: str | None = None
    extra_model_paths_config: str | None = None
    fast: bool = False
    disable_smart_memory: bool = False
    enable_cors_header: bool = False
    multi_user: bool = False
    disable_all_custom_nodes: bool = False
    enable_manager: bool = False


class ProfileLike(Protocol):
    executable_path: str
    working_dir: str | None
    host: str
    port: int
    engine_options: dict[str, Any]
    extra_args: list[str]


def parse_options(options: dict[str, Any]) -> Options:
    try:
        return Options.model_validate(options)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ValueError(f"Invalid ComfyUI options: {problems}") from exc


def validate(profile: ProfileLike) -> None:
    if not profile.working_dir:
        raise ValueError("ComfyUI needs its repository directory as the working directory")
    parse_options(profile.engine_options)


def build_argv(profile: ProfileLike) -> list[str]:
    """`executable_path` is uv; it runs main.py with the environment of the repository."""
    options = parse_options(profile.engine_options)
    argv = [profile.executable_path, "run", ENTRY_POINT]
    if profile.host:
        argv += ["--listen", profile.host]
    argv += ["--port", str(profile.port)]
    if options.vram_mode:
        argv.append(f"--{options.vram_mode}")
    for name, flag in VALUES.items():
        value = getattr(options, name)
        if value not in (None, ""):
            argv += [flag, f"{value:g}" if isinstance(value, float) else str(value)]
    argv += [flag for name, flag in SWITCHES.items() if getattr(options, name)]
    argv += split_extra_args(profile.extra_args)
    return argv


def working_dir(profile: ProfileLike) -> str | None:
    return profile.working_dir


def health_url(profile: ProfileLike) -> str:
    host = "127.0.0.1" if profile.host in LOOPBACK_FOR_WILDCARD else profile.host
    return f"http://{host}:{profile.port}/system_stats"
