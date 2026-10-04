from __future__ import annotations

from api_server.app.remote.executor import clean_line
from api_server.app.remote.gpu import GpuSampler, parse_apps, parse_gpu_line
from api_server.app.remote.logs import LogChannel


def test_parse_gpu_line() -> None:
    gpu = parse_gpu_line("1, GPU-abc, NVIDIA GeForce RTX 3090, 20311, 24576, 87, 71, 312.45")
    assert gpu == {
        "index": 1,
        "uuid": "GPU-abc",
        "name": "NVIDIA GeForce RTX 3090",
        "memory_used_mb": 20311.0,
        "memory_total_mb": 24576.0,
        "utilization_pct": 87.0,
        "temperature_c": 71.0,
        "power_w": 312.45,
    }


def test_parse_gpu_line_handles_unavailable_readings_and_noise() -> None:
    gpu = parse_gpu_line("0, GPU-abc, RTX 4090, 1024, 24564, 3, [N/A], [N/A]")
    assert gpu is not None
    assert gpu["temperature_c"] is None
    assert gpu["power_w"] is None
    assert parse_gpu_line("NVIDIA-SMI has failed") is None
    assert parse_gpu_line("") is None


def test_parse_apps_groups_by_gpu() -> None:
    apps = parse_apps("4242, 18000, GPU-a\n4242, 6000, GPU-b\n77, [N/A], GPU-a\nnoise\n")
    assert apps == {"GPU-a": [(4242, 18000.0), (77, None)], "GPU-b": [(4242, 6000.0)]}


def test_publish_attributes_vram_to_profiles() -> None:
    owners = {4242: ("prf_1", "qwen")}
    sampler = GpuSampler(
        executor=None,  # type: ignore[arg-type]
        history_samples=2,
        process_interval=1,
        resolve_pid=owners.get,
    )
    sampler._apps = {"GPU-a": [(4242, 18000.0), (77, 500.0)]}
    for _ in range(3):
        sampler.publish([parse_gpu_line("0, GPU-a, RTX, 18500, 24576, 50, 60, 200")])
    assert sampler.latest["gpus"][0]["processes"] == [
        {"pid": 4242, "used_mb": 18000.0, "profile_id": "prf_1", "profile_name": "qwen"},
        {"pid": 77, "used_mb": 500.0, "profile_id": None, "profile_name": None},
    ]
    # History is bounded, and sequence numbers keep counting past evicted samples.
    snapshots, seq = sampler.since(0)
    assert (len(snapshots), seq, sampler.first_seq) == (2, 3, 1)
    assert sampler.since(seq) == ([], 3)


def test_log_channel_sequence_and_reset() -> None:
    channel = LogChannel(max_lines=3)
    for index in range(5):
        channel.append(f"line {index}")
    assert channel.first_seq == 2
    assert channel.since(0) == (["line 2", "line 3", "line 4"], 5)
    assert channel.since(4) == (["line 4"], 5)
    assert channel.since(0, limit=2) == (["line 2", "line 3"], 4)
    generation = channel.generation
    channel.reset()
    assert channel.generation == generation + 1
    assert channel.since(channel.first_seq) == ([], 5)


def test_clean_line() -> None:
    assert clean_line("plain\r\n") == "plain"
    assert clean_line("\x1b[32mgreen\x1b[0m\n") == "green"
    assert clean_line("10%\r50%\r100%\n") == "100%"
