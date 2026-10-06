from __future__ import annotations

import shlex

import pytest

from api_server.app.remote.engines import comfyui, command_line, get_engine
from api_server.app.remote.engines.llama_cpp import (
    build_argv,
    health_url,
    split_extra_args,
    working_dir,
)
from api_server.app.remote.process import process_matches
from api_server.app.schemas import ProfileCreate


def make_profile(**overrides: object) -> ProfileCreate:
    values: dict[str, object] = {"name": "p", "executable_path": "/opt/llama/llama-server"}
    values.update(overrides)
    return ProfileCreate(**values)


def test_build_argv_includes_only_set_fields() -> None:
    assert build_argv(make_profile()) == [
        "/opt/llama/llama-server",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
    ]


def test_build_argv_full_profile() -> None:
    profile = make_profile(
        model_path="/models/My Model.gguf",
        alias="qwen",
        host="127.0.0.1",
        port=9001,
        ctx_size=32768,
        n_gpu_layers=99,
        extra_args=["--flash-attn on \\", "", "# comment", '--chat-template "a b"', "-np 4"],
    )
    assert build_argv(profile) == [
        "/opt/llama/llama-server",
        "--model",
        "/models/My Model.gguf",
        "--alias",
        "qwen",
        "--host",
        "127.0.0.1",
        "--port",
        "9001",
        "--ctx-size",
        "32768",
        "--n-gpu-layers",
        "99",
        "--flash-attn",
        "on",
        "--chat-template",
        "a b",
        "-np",
        "4",
    ]


def test_command_line_round_trips_through_a_shell() -> None:
    argv = build_argv(make_profile(model_path="/models/it's $HOME; rm -rf.gguf"))
    line = command_line(argv, {"CUDA_VISIBLE_DEVICES": "0,1", "NOTE": "a b"})
    assert shlex.split(line) == ["CUDA_VISIBLE_DEVICES=0,1", "NOTE=a b", *argv]


def test_split_extra_args_strips_continuations() -> None:
    assert split_extra_args(["  --temp 0.7 \\", "\\", "--jinja"]) == ["--temp", "0.7", "--jinja"]


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("0.0.0.0", "http://127.0.0.1:8080/health"),
        ("192.168.1.9", "http://192.168.1.9:8080/health"),
    ],
)
def test_health_url(host: str, expected: str) -> None:
    assert health_url(make_profile(host=host)) == expected


def test_working_dir_defaults_to_the_executable_folder() -> None:
    assert working_dir(make_profile()) == "/opt/llama"
    assert working_dir(make_profile(working_dir="/srv/models")) == "/srv/models"
    assert working_dir(make_profile(working_dir="  ")) == "/opt/llama"
    # A bare command found on PATH has no folder to move to.
    assert working_dir(make_profile(executable_path="llama-server")) is None


def test_command_line_shows_the_directory_change() -> None:
    line = command_line(["./llama-server"], {"A": "1"}, "/opt/my llama")
    assert line == "cd '/opt/my llama' && A=1 ./llama-server"
    assert command_line(["x"], {}, "~/llama.cpp/build") == "cd ~/llama.cpp/build && x"


def test_command_line_keeps_a_home_relative_executable_expandable() -> None:
    line = command_line(["~/.local/bin/uv", "run", "main.py", "~/a b"], {})
    assert line == "~/.local/bin/uv run main.py '~/a b'"


def test_unknown_engine_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported engine"):
        get_engine("vllm")
    with pytest.raises(ValueError, match="Unsupported engine"):
        make_profile(engine="vllm")


def test_invalid_extra_args_and_env_are_rejected() -> None:
    with pytest.raises(ValueError, match="Cannot parse"):
        make_profile(extra_args=['--template "unterminated'])
    with pytest.raises(ValueError, match="Invalid environment variable"):
        make_profile(env={"BAD NAME": "1"})


def make_comfyui(**overrides: object) -> ProfileCreate:
    values: dict[str, object] = {
        "engine": "comfyui",
        "executable_path": "uv",
        "working_dir": "~/ComfyUI",
        "port": 8188,
    }
    values.update(overrides)
    return make_profile(**values)


def test_comfyui_runs_main_through_uv_in_the_repository() -> None:
    profile = make_comfyui()
    assert comfyui.build_argv(profile) == [
        "uv",
        "run",
        "main.py",
        "--listen",
        "0.0.0.0",
        "--port",
        "8188",
    ]
    assert comfyui.working_dir(profile) == "~/ComfyUI"
    assert comfyui.health_url(profile) == "http://127.0.0.1:8188/system_stats"


def test_comfyui_options_become_flags() -> None:
    profile = make_comfyui(
        # llama.cpp settings mean nothing to ComfyUI.
        model_path="/models/x.gguf",
        ctx_size=4096,
        engine_options={
            "vram_mode": "lowvram",
            "preview_method": "taesd",
            "reserve_vram": 1.5,
            "output_directory": "/data/my output",
            "extra_model_paths_config": "",
            "enable_cors_header": True,
            "fast": True,
            "multi_user": False,
            "enable_manager": True,
        },
        extra_args=["--front-end-version Comfy-Org/ComfyUI_frontend@latest"],
    )
    assert comfyui.build_argv(profile)[7:] == [
        "--lowvram",
        "--preview-method",
        "taesd",
        "--reserve-vram",
        "1.5",
        "--output-directory",
        "/data/my output",
        "--fast",
        "--enable-cors-header",
        "--enable-manager",
        "--front-end-version",
        "Comfy-Org/ComfyUI_frontend@latest",
    ]


def test_engine_options_are_validated_per_engine() -> None:
    with pytest.raises(ValueError, match="repository directory"):
        make_comfyui(working_dir=None)
    with pytest.raises(ValueError, match="vram_mode"):
        make_comfyui(engine_options={"vram_mode": "turbo"})
    with pytest.raises(ValueError, match="no_such_option"):
        make_comfyui(engine_options={"no_such_option": 1})
    with pytest.raises(ValueError, match="no engine options"):
        make_profile(engine_options={"fast": True})


def test_process_matches_needs_the_executable_and_its_arguments() -> None:
    command = ["uv", "run", "main.py", "--port", "8188"]
    assert process_matches(command, "uv run main.py --port 8188")
    # A script is shown behind its interpreter.
    assert process_matches(["/opt/server.py", "--port", "1"], "python3 /opt/server.py --port 1")
    assert process_matches(["/opt/llama-server"], "/opt/llama-server")
    home_uv = ["~/.local/bin/uv", "run", "main.py"]
    assert process_matches(home_uv, "/home/me/.local/bin/uv run main.py")
    assert not process_matches(home_uv, "/usr/bin/uv run main.py")
    assert not process_matches(command, "uv run pytest")
    assert not process_matches(command, "/usr/bin/uvicorn app:main")
    assert not process_matches([], "uv run main.py")
