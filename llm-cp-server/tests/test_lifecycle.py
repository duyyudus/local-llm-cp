from __future__ import annotations

import asyncio
import os
import signal
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from conftest import STUB_SERVER, profile_payload
from sqlalchemy import select

from api_server.app.remote.executor import RemoteUnavailableError
from api_server.app.runtime import Runtime
from common.db.models import Run


def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A killed child of the test process lingers as a zombie until reaped.
    return "Z" not in Path(f"/proc/{pid}/stat").read_text().split(")")[-1].split()[0]


async def wait_for(predicate, timeout: float = 10.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        result = predicate()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return
        assert asyncio.get_running_loop().time() < deadline, "condition was not met in time"
        await asyncio.sleep(0.1)


async def create_and_start(client, **overrides: object) -> dict:
    profile = (await client.post("/profiles", json=profile_payload(**overrides))).json()
    started = await client.post(f"/profiles/{profile['id']}/start")
    assert started.status_code == 200, started.text
    return started.json()


async def status_of(client, runtime: Runtime, profile_id: str) -> str:
    await runtime.refresh()
    return (await client.get(f"/profiles/{profile_id}")).json()["run"]["status"]


async def test_start_stream_logs_and_stop(client, runtime: Runtime) -> None:
    profile = await create_and_start(
        client, extra_args=["--flag 'two words'"], env={"STUB_ENV": "from profile"}
    )
    pid = profile["run"]["pid"]
    assert profile["run"]["status"] == "starting"
    assert is_alive(pid)
    # The server leads its own process group, so stop can signal the whole group.
    assert os.getpgid(pid) == pid

    async def ready() -> bool:
        return await status_of(client, runtime, profile["id"]) == "ready"

    await wait_for(ready)

    channel = runtime.logs.channel(profile["id"])
    await wait_for(lambda: channel.next_seq >= 4)
    lines, _ = channel.since(0)
    assert lines[0].startswith("stub starting on 127.0.0.1:")
    assert lines[1] == "extra args: ['--flag', 'two words']"
    assert lines[2] == "STUB_ENV=from profile"

    again = await client.post(f"/profiles/{profile['id']}/start")
    assert again.status_code == 409
    assert (await client.delete(f"/profiles/{profile['id']}")).status_code == 409

    stopped = await client.post(f"/profiles/{profile['id']}/stop")
    assert stopped.status_code == 200
    assert stopped.json()["run"]["status"] == "stopped"
    await wait_for(lambda: not is_alive(pid))
    assert (await client.post(f"/profiles/{profile['id']}/stop")).status_code == 409
    assert (await client.delete(f"/profiles/{profile['id']}")).status_code == 204


async def test_port_conflict_between_running_profiles(client) -> None:
    first = await create_and_start(client, name="first")
    second = (
        await client.post("/profiles", json=profile_payload(name="second", port=first["port"]))
    ).json()
    conflict = await client.post(f"/profiles/{second['id']}/start")
    assert conflict.status_code == 409
    assert "in use by running profile 'first'" in conflict.json()["detail"]
    await client.post(f"/profiles/{first['id']}/stop")
    # Once the first one is stopped the port is free again.
    assert (await client.post(f"/profiles/{second['id']}/start")).status_code == 200
    await client.post(f"/profiles/{second['id']}/stop")


async def test_two_profiles_run_concurrently(client, runtime: Runtime) -> None:
    first = await create_and_start(client, name="first")
    second = await create_and_start(client, name="second")
    await runtime.refresh()
    assert set(runtime.live) == {first["id"], second["id"]}
    assert runtime.profile_for_pid(second["run"]["pid"]) == (second["id"], "second")
    for profile in (first, second):
        assert (await client.post(f"/profiles/{profile['id']}/stop")).status_code == 200


async def test_crashed_process_is_reported_as_exited(client, runtime: Runtime) -> None:
    profile = await create_and_start(client)
    pid = profile["run"]["pid"]
    os.killpg(pid, signal.SIGKILL)
    await wait_for(lambda: not is_alive(pid))
    assert await status_of(client, runtime, profile["id"]) == "exited"
    assert profile["id"] not in runtime.live
    # It can be started again after a crash.
    restarted = await client.post(f"/profiles/{profile['id']}/start")
    assert restarted.status_code == 200
    await client.post(f"/profiles/{profile['id']}/stop")


async def test_reused_pid_is_not_mistaken_for_the_run(
    client, runtime: Runtime, session_factory
) -> None:
    profile = await create_and_start(client)
    pid = profile["run"]["pid"]
    # Simulate the recorded pid now belonging to an unrelated program.
    async with session_factory() as session:
        run = await session.scalar(select(Run).where(Run.profile_id == profile["id"]))
        run.command = ["/somewhere/else/llama-server"]
        await session.commit()
    assert await status_of(client, runtime, profile["id"]) == "exited"
    assert is_alive(pid), "a process that is not ours must never be signalled"
    os.killpg(pid, signal.SIGKILL)


async def test_runs_are_reattached_after_app_restart(
    client, runtime: Runtime, settings, session_factory
) -> None:
    profile = await create_and_start(client)
    restarted = Runtime(settings, session_factory, executor=runtime.executor)
    try:
        await restarted.refresh()
        assert restarted.live[profile["id"]].pid == profile["run"]["pid"]
        channel = restarted.logs.channel(profile["id"])
        await wait_for(lambda: channel.next_seq >= 1)
        assert channel.since(0)[0][0].startswith("stub starting")
    finally:
        await restarted.logs.close()
    await client.post(f"/profiles/{profile['id']}/stop")


async def test_edit_while_running_flags_command_change(client, runtime: Runtime) -> None:
    profile = await create_and_start(client)
    assert profile["run"]["command_changed"] is False
    edited = await client.patch(f"/profiles/{profile['id']}", json={"ctx_size": 4096})
    assert edited.json()["run"]["command_changed"] is True
    await client.post(f"/profiles/{profile['id']}/stop")


async def test_server_runs_in_its_working_directory(client, tmp_path) -> None:
    default = await create_and_start(client, name="default")
    custom = await create_and_start(client, name="custom", working_dir=str(tmp_path))
    try:
        assert os.readlink(f"/proc/{default['run']['pid']}/cwd") == str(Path(STUB_SERVER).parent)
        assert os.readlink(f"/proc/{custom['run']['pid']}/cwd") == str(tmp_path)
    finally:
        for profile in (default, custom):
            await client.post(f"/profiles/{profile['id']}/stop")

    missing = (
        await client.post(
            "/profiles", json=profile_payload(name="missing", working_dir=str(tmp_path / "nope"))
        )
    ).json()
    response = await client.post(f"/profiles/{missing['id']}/start")
    assert response.status_code == 502
    assert "nope" in response.json()["detail"]


async def test_missing_executable_is_rejected(client) -> None:
    profile = (
        await client.post("/profiles", json=profile_payload(executable_path="/nope/llama-server"))
    ).json()
    response = await client.post(f"/profiles/{profile['id']}/start")
    assert response.status_code == 400
    assert "/nope/llama-server" in response.json()["detail"]


async def test_log_is_rotated_and_backlog_loaded_for_stopped_profile(
    client, runtime: Runtime
) -> None:
    profile = await create_and_start(client)
    await wait_for(lambda: runtime.logs.channel(profile["id"]).next_seq >= 4)
    await client.post(f"/profiles/{profile['id']}/stop")
    seen = runtime.logs.channel(profile["id"]).next_seq
    await client.post(f"/profiles/{profile['id']}/start")
    await wait_for(lambda: runtime.logs.channel(profile["id"]).next_seq >= seen + 4)
    await client.post(f"/profiles/{profile['id']}/stop")
    log_dir = Path(await runtime.processes.state_dir()) / profile["id"]
    assert sorted(path.name for path in log_dir.iterdir()) == ["server.log", "server.log.1"]

    # After an app restart nothing is buffered; the last log is read on demand.
    runtime.logs.forget(profile["id"])
    await runtime.logs.load_backlog(profile["id"], str(log_dir / "server.log"))
    lines, _ = runtime.logs.channel(profile["id"]).since(0)
    assert lines[0].startswith("stub starting")


async def test_deleting_a_profile_removes_its_logs(client, runtime: Runtime) -> None:
    keep = await create_and_start(client, name="keep")
    gone = await create_and_start(client, name="gone")
    state_dir = Path(await runtime.processes.state_dir())
    for profile in (keep, gone):
        await client.post(f"/profiles/{profile['id']}/stop")
    assert (state_dir / gone["id"] / "server.log").exists()

    assert (await client.delete(f"/profiles/{gone['id']}")).status_code == 204
    assert not (state_dir / gone["id"]).exists()
    # Only that profile's folder goes; the others are untouched.
    assert (state_dir / keep["id"] / "server.log").exists()


async def test_profile_is_deleted_even_when_host_is_offline(client, runtime: Runtime) -> None:
    profile = await create_and_start(client)
    await client.post(f"/profiles/{profile['id']}/stop")
    log_dir = Path(await runtime.processes.state_dir()) / profile["id"]
    online = runtime.processes._executor
    runtime.processes._executor = OfflineExecutor()
    try:
        assert (await client.delete(f"/profiles/{profile['id']}")).status_code == 204
    finally:
        runtime.processes._executor = online
    assert (await client.get(f"/profiles/{profile['id']}")).status_code == 404
    assert log_dir.exists()


async def test_remove_logs_rejects_unexpected_ids(runtime: Runtime) -> None:
    state_dir = Path(await runtime.processes.state_dir())
    state_dir.mkdir(parents=True, exist_ok=True)
    for bad in ("", ".", "..", "a/b", "../x"):
        with pytest.raises(ValueError):
            await runtime.processes.remove_logs(bad)
    assert state_dir.exists()


class OfflineExecutor:
    async def run(self, command: str, timeout: float = 15.0):
        raise RemoteUnavailableError("connection refused")

    async def stream(self, command: str) -> AsyncIterator[str]:
        raise RemoteUnavailableError("connection refused")
        yield ""

    async def close(self) -> None:
        return None


async def test_host_offline(client, runtime: Runtime) -> None:
    profile = await create_and_start(client)
    pid = profile["run"]["pid"]
    online = runtime.processes._executor
    runtime.processes._executor = OfflineExecutor()
    try:
        # The run is kept open and shown as unknown rather than declared dead.
        assert await status_of(client, runtime, profile["id"]) == "unknown"
        response = await client.post(f"/profiles/{profile['id']}/stop")
        assert response.status_code == 503
        assert "GPU host unavailable" in response.json()["detail"]
    finally:
        runtime.processes._executor = online
    assert is_alive(pid)
    assert await status_of(client, runtime, profile["id"]) in {"starting", "ready"}
    await client.post(f"/profiles/{profile['id']}/stop")
