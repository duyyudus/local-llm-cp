# local-llm-cp

A small web control panel for running [llama.cpp](https://github.com/ggml-org/llama.cpp)
servers on a GPU machine. It replaces a folder of launch scripts and the two SSH windows
(one for `llama-server`, one for `nvtop`) with one page:

- **Profiles**: a saved server executable plus its arguments and environment variables.
  Create, edit, duplicate, delete, start and stop. Export to and import from JSON.
- **Console**: the live log of each running server, as you would see it in a terminal.
- **GPUs**: per-GPU VRAM and compute usage, temperature, power, and which running profile
  holds how much VRAM.

## How it works

The app runs anywhere on your network and controls the GPU host over SSH. Nothing is
installed on the GPU host; it needs `bash`, `nvidia-smi`, and optionally `curl` (used to
tell "loading" from "ready").

Servers are started detached, so they keep running if the app restarts or the connection
drops. The app picks them up again when it comes back. Each profile logs to
`~/.local/state/local-llm-cp/<profile id>/server.log` on the GPU host, with the previous
five logs kept. Deleting a profile also deletes its log folder.

There is no login. Run it only on a network you trust.

## Run with Docker

```bash
cp .env.local.example .env.local
# edit .env.local: GPU_SSH_HOST, GPU_SSH_USER, and GPU_SSH_KEY_FILE or GPU_SSH_PASSWORD
./docker-build local --env-file .env.local
```

Then open `http://<docker host>:3050`. The API is published on port `8040`. Profiles are
stored in a SQLite file in the `llm-cp-data` Docker volume.

Authentication is by key, password, or both. `GPU_SSH_KEY_FILE` is a private key on the
Docker host whose public key is in the GPU host's `~/.ssh/authorized_keys`; leave it empty
and set `GPU_SSH_PASSWORD` to log in with the user's password instead. The password sits in
plain text in `.env.local`, so a key is the safer choice. Host key checking is off unless
`GPU_SSH_KNOWN_HOSTS` is set.

## Profiles

Common settings have their own fields: executable, model path, alias, host, port, context
size and GPU layers. Anything else goes in **Extra arguments**, one flag per line, so lines
from an existing script can be pasted as they are:

```
--flash-attn on \
--parallel 2
--jinja
```

Use the `CUDA_VISIBLE_DEVICES` environment variable to pin a profile to specific GPUs. The
form shows the exact command that will be run.

Several profiles can run at once as long as their ports differ. Editing a running profile
takes effect at its next start.

Profiles can be exported to a JSON file, one at a time or all together, and imported on
another install. The file holds launch settings only, including environment variables, so
check it for secrets before sharing. When an imported name already exists you choose
whether to skip it, keep both, or overwrite the existing profile. The same is available
from the API as `GET /profiles/export` and `POST /profiles/import?on_conflict=skip|rename|overwrite`.

## Development

Backend (Python 3.12, [uv](https://docs.astral.sh/uv/)):

```bash
cd llm-cp-server
cp .env.example .env      # set REMOTE_MODE=local to work without a GPU host
../run-server.sh           # API on port 8040, with auto-reload
uv run pytest
uv run ruff check .
```

Dashboard (Node 22):

```bash
cd dashboard
npm install
../run-ui.sh              # http://localhost:5173, calls the API on port 8040
npm run test
npm run lint
```

See [AGENTS.md](AGENTS.md) for the code layout and conventions.
