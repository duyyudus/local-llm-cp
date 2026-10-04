import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Profile } from "./api";
import { App } from "./app/App";

class MockEventSource {
  static instances: MockEventSource[] = [];
  listeners: Record<string, ((event: MessageEvent) => void)[]> = {};
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(public url: string) {
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    (this.listeners[type] ??= []).push(listener);
  }

  emit(type: string, data: unknown) {
    for (const listener of this.listeners[type] ?? []) {
      listener({ data: JSON.stringify(data) } as MessageEvent);
    }
  }

  close() {
    this.closed = true;
  }

  static find(fragment: string): MockEventSource {
    const match = MockEventSource.instances.filter(
      (source) => source.url.includes(fragment) && !source.closed,
    );
    return match[match.length - 1];
  }
}

function makeProfile(overrides: Partial<Profile> = {}): Profile {
  return {
    id: "prf_1",
    name: "qwen",
    engine: "llama.cpp",
    executable_path: "/opt/llama-server",
    working_dir: null,
    model_path: "/models/qwen-coder.gguf",
    alias: "qwen",
    host: "0.0.0.0",
    port: 8080,
    ctx_size: 32768,
    n_gpu_layers: null,
    extra_args: [],
    env: {},
    notes: "",
    command: "/opt/llama-server --model /models/qwen-coder.gguf",
    run: { status: "stopped", pid: null, started_at: null, stopped_at: null, command_changed: false },
    created_at: "2026-10-04T00:00:00Z",
    updated_at: "2026-10-04T00:00:00Z",
    ...overrides,
  };
}

let profiles: Profile[] = [];
let hostConnected = true;
const calls: { method: string; path: string; body?: unknown }[] = [];

function mockFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const path = new URL(String(input)).pathname;
  const method = init?.method ?? "GET";
  const body = init?.body ? JSON.parse(String(init.body)) : undefined;
  calls.push({ method, path, body });
  const json = (data: unknown, status = 200) =>
    Promise.resolve(new Response(JSON.stringify(data), { status }));

  if (path === "/host") {
    return json({
      mode: "ssh",
      target: "me@gpu:22",
      connected: hostConnected,
      error: null,
      gpu_error: null,
    });
  }
  if (path === "/host/shutdown") {
    return Promise.resolve(new Response(null, { status: 204 }));
  }
  if (path === "/profiles" && method === "GET") {
    return json({ items: profiles, total: profiles.length });
  }
  if (path === "/profiles/export") {
    const payloads = profiles.map(({ id, command, run, created_at, updated_at, ...rest }) => rest);
    return json({ format: "llm-cp-profiles", version: 1, exported_at: null, profiles: payloads });
  }
  if (path === "/profiles/import") {
    return json({ created: ["gemma"], updated: [], skipped: ["qwen"] });
  }
  if (path === "/profiles/preview-command") {
    return json({ command: `${body.executable_path} --port ${body.port}`, argv: [] });
  }
  if (path === "/profiles" && method === "POST") {
    profiles = [...profiles, makeProfile({ ...body, id: "prf_new" })];
    return json(profiles[profiles.length - 1], 201);
  }
  if (path.endsWith("/start")) {
    if (profiles[0].port === 9999) return json({ detail: "Port 9999 is in use" }, 409);
    profiles = profiles.map((profile) => ({
      ...profile,
      run: { ...profile.run, status: "starting", pid: 4242, started_at: new Date().toISOString() },
    }));
    return json(profiles[0]);
  }
  if (path.endsWith("/stop")) {
    profiles = profiles.map((profile) => ({
      ...profile,
      run: { ...profile.run, status: "stopped", pid: null },
    }));
    return json(profiles[0]);
  }
  return json({ detail: "not mocked" }, 404);
}

beforeEach(() => {
  profiles = [];
  hostConnected = true;
  calls.length = 0;
  MockEventSource.instances = [];
  localStorage.clear();
  vi.stubGlobal("EventSource", MockEventSource);
  vi.stubGlobal("fetch", vi.fn(mockFetch));
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) =>
    window.setTimeout(() => callback(0), 0),
  );
  vi.stubGlobal("cancelAnimationFrame", (handle: number) => window.clearTimeout(handle));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("lists profiles with their settings and the host connection", async () => {
    profiles = [makeProfile()];
    render(<App />);
    const row = (await screen.findByText("qwen")).closest("li")!;
    expect(within(row).getByText("qwen-coder.gguf")).toBeInTheDocument();
    expect(within(row).getByText("0.0.0.0:8080")).toBeInTheDocument();
    expect(within(row).getByText("ctx 32768")).toBeInTheDocument();
    expect(within(row).getByText("stopped")).toBeInTheDocument();
    expect(await screen.findByText("me@gpu:22")).toBeInTheDocument();
  });

  it("starts a profile and streams its log into the console", async () => {
    profiles = [makeProfile()];
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Start" }));
    await waitFor(() => expect(screen.getAllByText("loading").length).toBeGreaterThan(0));
    expect(calls.some((call) => call.path === "/profiles/prf_1/start")).toBe(true);

    const source = MockEventSource.find("/profiles/prf_1/logs/stream");
    act(() => {
      source.emit("reset", {});
      source.emit("lines", { lines: ["loading model", "server is listening"] });
    });
    await waitFor(() =>
      expect(screen.getByTestId("console-output")).toHaveTextContent(
        "loading model server is listening",
      ),
    );
    // A relaunch resets the view instead of appending to the old run's output.
    act(() => {
      source.emit("reset", {});
      source.emit("lines", { lines: ["second launch"] });
    });
    await waitFor(() =>
      expect(screen.getByTestId("console-output")).toHaveTextContent(/^second launch$/),
    );
  });

  it("asks for confirmation before stopping", async () => {
    profiles = [
      makeProfile({
        run: {
          status: "ready",
          pid: 4242,
          started_at: new Date().toISOString(),
          stopped_at: null,
          command_changed: true,
        },
      }),
    ];
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));
    expect(calls.some((call) => call.path.endsWith("/stop"))).toBe(false);
    expect(screen.getByText("Edited since launch. Restart to apply.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Stop server" }));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith("/stop"))).toBe(true));
    await screen.findByRole("button", { name: "Start" });
  });

  it("shuts the host down after confirmation", async () => {
    render(<App />);
    await screen.findByText("me@gpu:22");
    const button = screen.getByRole("button", { name: "Shut down host" });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    expect(calls.some((call) => call.path === "/host/shutdown")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Shut down" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Shutdown requested");
    expect(calls.some((call) => call.path === "/host/shutdown" && call.method === "POST")).toBe(
      true,
    );
  });

  it("disables the shutdown button while the host is offline", async () => {
    hostConnected = false;
    render(<App />);
    await screen.findByText(/me@gpu:22 offline/);
    expect(screen.getByRole("button", { name: "Shut down host" })).toBeDisabled();
  });

  it("shows the backend error when a start is refused", async () => {
    profiles = [makeProfile({ port: 9999 })];
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Start" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("qwen: Port 9999 is in use");
  });

  it("creates a profile from the form with a command preview", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "New profile" }));
    const create = screen.getByRole("button", { name: "Create profile" });
    expect(create).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Profile name"), { target: { value: "new one" } });
    fireEvent.change(screen.getByPlaceholderText("/path/to/llama-server"), {
      target: { value: "/opt/llama-server" },
    });
    fireEvent.change(screen.getByLabelText("Port"), { target: { value: "9001" } });
    fireEvent.change(screen.getByLabelText("Extra arguments", { exact: false }), {
      target: { value: "--jinja\n--parallel 2" },
    });
    await waitFor(() =>
      expect(screen.getByTestId("command-preview")).toHaveTextContent(
        "/opt/llama-server --port 9001",
      ),
    );
    fireEvent.click(create);
    await screen.findByText("new one");
    const created = calls.find((call) => call.method === "POST" && call.path === "/profiles");
    expect(created?.body).toMatchObject({
      name: "new one",
      port: 9001,
      model_path: null,
      extra_args: ["--jinja", "--parallel 2"],
    });
  });

  it("exports all profiles to a JSON download", async () => {
    profiles = [makeProfile()];
    const blobs: Blob[] = [];
    URL.createObjectURL = vi.fn((blob: Blob) => (blobs.push(blob), "blob:export"));
    URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<App />);
    await screen.findByText("qwen");
    fireEvent.click(screen.getByRole("button", { name: "Export all profiles" }));
    await waitFor(() => expect(click).toHaveBeenCalled());
    const exported = JSON.parse(await blobs[0].text());
    expect(exported.format).toBe("llm-cp-profiles");
    expect(exported.profiles[0]).toMatchObject({ name: "qwen", port: 8080 });
    expect(exported.profiles[0]).not.toHaveProperty("id");
    click.mockRestore();
  });

  it("asks how to handle existing profiles before importing", async () => {
    profiles = [makeProfile()];
    render(<App />);
    await screen.findByText("qwen");
    const document = {
      format: "llm-cp-profiles",
      version: 1,
      profiles: [{ name: "qwen" }, { name: "gemma" }],
    };
    fireEvent.change(screen.getByTestId("import-file"), {
      target: { files: [new File([JSON.stringify(document)], "profiles.json")] },
    });
    const dialog = await screen.findByRole("dialog", { name: "Import profiles" });
    expect(dialog).toHaveTextContent("1 of 2 profiles in this file already exist");
    expect(calls.some((call) => call.path === "/profiles/import")).toBe(false);
    fireEvent.click(within(dialog).getByRole("button", { name: "Skip existing" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Import finished: 1 created, 1 skipped.",
    );
    const imported = calls.find((call) => call.path === "/profiles/import");
    expect(imported?.body).toMatchObject({ profiles: [{ name: "qwen" }, { name: "gemma" }] });
  });

  it("rejects a file that is not a profile export", async () => {
    render(<App />);
    await screen.findByRole("button", { name: "Import profiles" });
    fireEvent.change(screen.getByTestId("import-file"), {
      target: { files: [new File(["{}"], "other.json")] },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Import: The file is not a profile export",
    );
  });

  it("renders GPU meters from the stream", async () => {
    render(<App />);
    await screen.findByText("Waiting for GPU data", { exact: false }).catch(() => null);
    const gpu = {
      index: 0,
      uuid: "GPU-a",
      name: "NVIDIA GeForce RTX 3090",
      memory_used_mb: 12288,
      memory_total_mb: 24576,
      utilization_pct: 87,
      temperature_c: 71,
      power_w: 312,
      processes: [{ pid: 4242, used_mb: 11264, profile_id: "prf_1", profile_name: "qwen" }],
    };
    act(() => {
      MockEventSource.find("/host/stream").emit("gpu_history", {
        snapshots: [{ ts: 1, gpus: [gpu] }],
      });
    });
    expect(screen.getByText("GeForce RTX 3090", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("12.0 / 24.0 GiB")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Compute 87%" })).toHaveAttribute(
      "aria-valuenow",
      "87",
    );
    expect(screen.getByText("11.0 GiB")).toBeInTheDocument();
  });

  it("renders CPU and memory meters next to the GPUs", async () => {
    render(<App />);
    expect(await screen.findAllByText("Connecting to the API")).toHaveLength(2);
    const system = {
      ts: 1,
      cpu_name: "AMD Ryzen 9 5950X 16-Core Processor",
      cpu_threads: 32,
      cpu_utilization_pct: 42.4,
      memory_used_mb: 49152,
      memory_total_mb: 65536,
      swap_used_mb: 1024,
      swap_total_mb: 8192,
      processes: [{ pid: 4242, rss_mb: 21504, profile_id: "prf_1", profile_name: "qwen" }],
    };
    const source = MockEventSource.find("/host/stream");
    act(() => {
      source.emit("system_history", { snapshots: [system] });
      source.emit("system_snapshot", { ...system, ts: 2, cpu_utilization_pct: 90 });
    });
    expect(screen.getByText("AMD Ryzen 9 5950X 16-Core Processor")).toBeInTheDocument();
    expect(screen.getByText("48.0 / 64.0 GiB")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "CPU 90%" })).toHaveAttribute(
      "aria-valuenow",
      "90",
    );
    expect(screen.getByText("swap 1.0 / 8.0 GiB", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("21.0 GiB")).toBeInTheDocument();
    // The GPU side reports its own failure without hiding the system card.
    act(() => source.emit("gpu_status", { error: "nvidia-smi failed: not found" }));
    expect(screen.getByText("nvidia-smi failed: not found")).toBeInTheDocument();
    expect(screen.getByText("48.0 / 64.0 GiB")).toBeInTheDocument();
  });
});
