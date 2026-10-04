from __future__ import annotations

import shlex

import pytest

from api_server.app.remote.engines import command_line, get_engine
from api_server.app.remote.engines.llama_cpp import (
    build_argv,
    health_url,
    split_extra_args,
    working_dir,
)
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
