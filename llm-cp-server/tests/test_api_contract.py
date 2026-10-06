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


async def test_export_profiles(client) -> None:
    payload = profile_payload(
        name="qwen", model_path="/models/qwen.gguf", extra_args=["--jinja"], env={"A": "1"}
    )
    qwen = (await client.post("/profiles", json=payload)).json()
    await client.post("/profiles", json=profile_payload(name="gemma"))

    exported = await client.get("/profiles/export")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    document = exported.json()
    assert (document["format"], document["version"]) == ("llm-cp-profiles", 1)
    assert [item["name"] for item in document["profiles"]] == ["gemma", "qwen"]
    # Only launch settings travel; ids, run state and timestamps stay behind.
    assert document["profiles"][1] == {
        "name": "qwen",
        "engine": "llama.cpp",
        "executable_path": payload["executable_path"],
        "working_dir": None,
        "model_path": "/models/qwen.gguf",
        "alias": None,
        "host": "127.0.0.1",
        "port": payload["port"],
        "ctx_size": None,
        "n_gpu_layers": None,
        "engine_options": {},
        "extra_args": ["--jinja"],
        "env": {"A": "1"},
        "notes": "",
    }

    single = (await client.get("/profiles/export", params={"id": qwen["id"]})).json()
    assert [item["name"] for item in single["profiles"]] == ["qwen"]
    assert (await client.get("/profiles/export", params={"id": "prf_nope"})).status_code == 404


async def test_import_profiles(client) -> None:
    await client.post("/profiles", json=profile_payload(name="qwen", port=9001))
    document = (await client.get("/profiles/export")).json()
    document["profiles"][0]["port"] = 9002
    document["profiles"].append(profile_payload(name="gemma", port=9003))

    skipped = (await client.post("/profiles/import", json=document)).json()
    assert skipped == {"created": ["gemma"], "updated": [], "skipped": ["qwen"]}

    renamed = await client.post("/profiles/import", json=document, params={"on_conflict": "rename"})
    assert renamed.json() == {
        "created": ["qwen (imported)", "gemma (imported)"],
        "updated": [],
        "skipped": [],
    }

    document["profiles"] = document["profiles"][:1]
    overwritten = await client.post(
        "/profiles/import", json=document, params={"on_conflict": "overwrite"}
    )
    assert overwritten.json() == {"created": [], "updated": ["qwen"], "skipped": []}
    ports = {item["name"]: item["port"] for item in (await client.get("/profiles")).json()["items"]}
    assert ports == {
        "qwen": 9002,
        "qwen (imported)": 9002,
        "gemma": 9003,
        "gemma (imported)": 9003,
    }


async def test_import_rejects_invalid_documents(client) -> None:
    document = {
        "format": "llm-cp-profiles",
        "version": 1,
        "profiles": [profile_payload(name="ok"), profile_payload(name="bad", port=70000)],
    }
    assert (await client.post("/profiles/import", json=document)).status_code == 422
    # Nothing is imported when any profile in the file is invalid.
    assert (await client.get("/profiles")).json()["total"] == 0
    document["profiles"].pop()
    newer = await client.post("/profiles/import", json={**document, "version": 2})
    assert newer.status_code == 422
    assert (await client.post("/profiles/import", json={"profiles": []})).status_code == 422
    assert (await client.post("/profiles/import", json=document)).status_code == 200


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


async def test_host_shutdown(client, runtime, tmp_path: Path) -> None:
    runtime.settings.gpu_ssh_password = "hunter2"
    response = await client.post("/host/shutdown")
    assert response.status_code == 204
    # The password reaches the command on stdin, as `sudo -S` expects.
    assert (tmp_path / "shutdown-requested").read_text() == "hunter2\n"

    runtime.settings.host_shutdown_command = "echo 'sudo: a password is required' >&2; exit 1"
    refused = await client.post("/host/shutdown")
    assert refused.status_code == 502
    assert refused.json()["detail"] == "Shutdown command failed: sudo: a password is required"


async def test_comfyui_profile_validation(client) -> None:
    payload = profile_payload(
        name="comfy",
        engine="comfyui",
        executable_path="uv",
        working_dir="/srv/ComfyUI",
        port=8188,
        engine_options={"vram_mode": "lowvram", "fast": True},
    )
    created = await client.post("/profiles", json=payload)
    assert created.status_code == 201, created.text
    profile = created.json()
    assert profile["command"] == (
        "cd /srv/ComfyUI && uv run main.py --listen 127.0.0.1 --port 8188 --lowvram --fast"
    )
    clone = (await client.post(f"/profiles/{profile['id']}/duplicate")).json()
    assert clone["engine_options"] == {"vram_mode": "lowvram", "fast": True}

    for bad in ({"working_dir": None}, {"engine_options": {"vram_mode": "turbo"}}):
        invalid = await client.post("/profiles", json={**payload, "name": "x", **bad})
        assert invalid.status_code == 422
    rejected = await client.patch(f"/profiles/{profile['id']}", json={"working_dir": ""})
    assert rejected.status_code == 422
    assert "repository directory" in rejected.json()["detail"]
    # Options of one engine do not carry over to another.
    rejected = await client.patch(f"/profiles/{profile['id']}", json={"engine": "llama.cpp"})
    assert rejected.status_code == 422
    switched = await client.patch(
        f"/profiles/{profile['id']}", json={"engine": "llama.cpp", "engine_options": {}}
    )
    assert switched.status_code == 200
