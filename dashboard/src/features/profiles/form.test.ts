import { describe, expect, it } from "vitest";

import type { Profile } from "../../api";
import { emptyForm, formFromProfile, payloadFromForm, validateForm, withEngine } from "./form";

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
  engine_options: {},
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

  it("round-trips a ComfyUI profile and leaves out unset options", () => {
    const comfy: Profile = {
      ...profile,
      engine: "comfyui",
      executable_path: "/opt/uv",
      working_dir: "/srv/ComfyUI",
      model_path: null,
      ctx_size: null,
      port: 8188,
      engine_options: {
        vram_mode: "lowvram",
        reserve_vram: 1.5,
        output_directory: "/data/out",
        fast: true,
      },
      extra_args: ["--verbose DEBUG"],
    };
    const form = formFromProfile(comfy);
    expect(form.comfy).toMatchObject({
      vram_mode: "lowvram",
      reserve_vram: "1.5",
      multi_user: false,
    });
    const { id, command, run, created_at, updated_at, ...expected } = comfy;
    expect(payloadFromForm(form)).toEqual(expected);
  });

  it("keeps llama.cpp settings out of a ComfyUI payload and the other way round", () => {
    const form = {
      ...emptyForm,
      name: "a",
      executable_path: "/bin/x",
      model_path: "/models/a.gguf",
      ctx_size: "4096",
      comfy: { ...emptyForm.comfy, vram_mode: "lowvram" },
    };
    expect(payloadFromForm(form).engine_options).toEqual({});
    const payload = payloadFromForm({ ...withEngine(form, "comfyui"), working_dir: "/srv/ComfyUI" });
    expect(payload).toMatchObject({
      engine: "comfyui",
      executable_path: "~/.local/bin/uv",
      model_path: null,
      ctx_size: null,
      engine_options: { vram_mode: "lowvram" },
    });
  });

  it("switches the launch target and default port with the engine", () => {
    const comfy = withEngine({ ...emptyForm, executable_path: "/opt/llama-server" }, "comfyui");
    expect([comfy.executable_path, comfy.working_dir, comfy.port]).toEqual(["", "", "8188"]);
    expect(withEngine(comfy, "llama.cpp").port).toBe("8080");
    expect(withEngine({ ...emptyForm, port: "9001" }, "comfyui").port).toBe("9001");
  });

  it("validates ComfyUI fields", () => {
    const valid = {
      ...withEngine({ ...emptyForm, name: "a" }, "comfyui"),
      working_dir: "/srv/ComfyUI",
    };
    expect(validateForm({ ...valid, working_dir: " " })).toBe("ComfyUI directory is required");
    // An empty uv field means the default path, which is shown as empty again when editing.
    expect(validateForm(valid)).toBeNull();
    const saved = payloadFromForm(valid);
    expect(saved.executable_path).toBe("~/.local/bin/uv");
    expect(formFromProfile({ ...profile, ...saved }).executable_path).toBe("");
    expect(validateForm({ ...valid, comfy: { ...valid.comfy, reserve_vram: "lots" } })).toBe(
      "Reserved VRAM must be a number of GB",
    );
    // llama.cpp fields are not checked for another engine.
    expect(validateForm({ ...valid, ctx_size: "8k" })).toBeNull();
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
