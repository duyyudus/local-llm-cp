import { describe, expect, it } from "vitest";

import type { Profile } from "../../api";
import { emptyForm, formFromProfile, payloadFromForm, validateForm } from "./form";

const profile: Profile = {
  id: "prf_1",
  name: "qwen",
  engine: "llama.cpp",
  executable_path: "/opt/llama-server",
  working_dir: null,
  model_path: "/models/qwen.gguf",
  alias: null,
  host: "0.0.0.0",
  port: 8080,
  ctx_size: 32768,
  n_gpu_layers: null,
  extra_args: ["--jinja", "--parallel 2"],
  env: { CUDA_VISIBLE_DEVICES: "0,1" },
  notes: "",
  command: "",
  run: { status: "stopped", pid: null, started_at: null, stopped_at: null, command_changed: false },
  created_at: "2026-10-04T00:00:00Z",
  updated_at: "2026-10-04T00:00:00Z",
};

describe("profile form", () => {
  it("round-trips a profile through the form", () => {
    const payload = payloadFromForm(formFromProfile(profile));
    const { id, command, run, created_at, updated_at, ...expected } = profile;
    expect(payload).toEqual(expected);
  });

  it("turns blank optional fields into nulls and drops empty rows", () => {
    const payload = payloadFromForm({
      ...emptyForm,
      name: "a",
      executable_path: "/bin/x",
      extra_args: "--one\n\n  \n--two 2",
      env: [
        { key: "", value: "ignored" },
        { key: " A ", value: "1" },
      ],
    });
    expect(payload.model_path).toBeNull();
    expect(payload.ctx_size).toBeNull();
    expect(payload.n_gpu_layers).toBeNull();
    expect(payload.extra_args).toEqual(["--one", "--two 2"]);
    expect(payload.env).toEqual({ A: "1" });
  });

  it("validates required and numeric fields", () => {
    const valid = { ...emptyForm, name: "a", executable_path: "/bin/x" };
    expect(validateForm(emptyForm)).toBe("Name is required");
    expect(validateForm({ ...valid, executable_path: " " })).toBe("Executable path is required");
    expect(validateForm({ ...valid, port: "70000" })).toBe("Port must be 1 to 65535");
    expect(validateForm({ ...valid, ctx_size: "8k" })).toBe("Context size must be a whole number");
    expect(validateForm(valid)).toBeNull();
  });
});
