from __future__ import annotations

from pathlib import Path

from conftest import STUB_SERVER, profile_payload


async def test_health_and_host(client) -> None:
    assert (await client.get("/health")).json()["status"] == "ok"
    ready = (await client.get("/ready")).json()
    assert ready == {"status": "ready", "database": "ok", "host_connected": True}
    host = (await client.get("/host")).json()
    assert host["mode"] == "local"
    assert host["connected"] is True


async def test_profile_crud(client) -> None:
    payload = profile_payload(
        name="qwen",
        model_path="/models/qwen.gguf",
        ctx_size=8192,
        extra_args=["--jinja"],
        env={"CUDA_VISIBLE_DEVICES": "0"},
    )
    created = await client.post("/profiles", json=payload)
    assert created.status_code == 201
    profile = created.json()
    assert profile["run"] == {
        "status": "stopped",
        "pid": None,
        "started_at": None,
        "stopped_at": None,
        "command_changed": False,
    }
    stub_dir = str(Path(STUB_SERVER).parent)
    assert profile["command"].startswith(f"cd {stub_dir} && CUDA_VISIBLE_DEVICES=0 ")
    assert profile["command"].endswith("--ctx-size 8192 --jinja")
    assert profile["created_at"].endswith("Z")

    listing = (await client.get("/profiles")).json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == profile["id"]

    updated = await client.patch(
        f"/profiles/{profile['id']}", json={"alias": "q", "ctx_size": None, "model_path": ""}
    )
    assert updated.status_code == 200
    body = updated.json()
    assert (body["alias"], body["ctx_size"], body["model_path"]) == ("q", None, None)
    assert body["name"] == "qwen"

    assert (await client.delete(f"/profiles/{profile['id']}")).status_code == 204
    assert (await client.get(f"/profiles/{profile['id']}")).status_code == 404


async def test_profile_name_must_be_unique(client) -> None:
    assert (await client.post("/profiles", json=profile_payload(name="a"))).status_code == 201
    other = await client.post("/profiles", json=profile_payload(name="b"))
    assert (await client.post("/profiles", json=profile_payload(name="a"))).status_code == 409
    rename = await client.patch(f"/profiles/{other.json()['id']}", json={"name": "a"})
    assert rename.status_code == 409


async def test_duplicate_profile(client) -> None:
    source = (
        await client.post(
            "/profiles", json=profile_payload(name="base", extra_args=["-np 2"], env={"A": "1"})
        )
    ).json()
    first = (await client.post(f"/profiles/{source['id']}/duplicate")).json()
    second = (await client.post(f"/profiles/{source['id']}/duplicate")).json()
    assert (first["name"], second["name"]) == ("base (copy)", "base (copy 2)")
    assert first["id"] != source["id"]
    assert (first["extra_args"], first["env"], first["port"]) == (
        ["-np 2"],
        {"A": "1"},
        source["port"],
    )


async def test_preview_command_and_validation(client) -> None:
    preview = await client.post(
        "/profiles/preview-command",
        json=profile_payload(executable_path="/bin/llama server", port=9000, host="0.0.0.0"),
    )
    assert preview.status_code == 200
    assert preview.json()["command"] == "cd /bin && '/bin/llama server' --host 0.0.0.0 --port 9000"

    assert (await client.post("/profiles", json=profile_payload(port=70000))).status_code == 422
    assert (await client.post("/profiles", json=profile_payload(name=" "))).status_code == 422
    bad_args = await client.post("/profiles", json=profile_payload(extra_args=['"open']))
    assert bad_args.status_code == 422


async def test_browse(client, tmp_path) -> None:
    (tmp_path / "models").mkdir()
    (tmp_path / "a.gguf").write_bytes(b"1234")
    listing = (await client.get("/host/browse", params={"path": str(tmp_path)})).json()
    assert listing["path"] == str(tmp_path)
    assert listing["parent"] == str(tmp_path.parent)
    by_name = {entry["name"]: entry for entry in listing["entries"]}
    assert by_name["models"]["is_dir"] is True
    assert by_name["a.gguf"] == {"name": "a.gguf", "is_dir": False, "size": 4}
    assert listing["entries"][0]["name"] == "models"
    missing = await client.get("/host/browse", params={"path": str(tmp_path / "nope")})
    assert missing.status_code == 404
