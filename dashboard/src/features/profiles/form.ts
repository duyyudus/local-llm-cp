import type { Profile, ProfilePayload } from "../../api";

export type EnvRow = { key: string; value: string };

export type ProfileFormState = {
  name: string;
  executable_path: string;
  working_dir: string;
  model_path: string;
  alias: string;
  host: string;
  port: string;
  ctx_size: string;
  n_gpu_layers: string;
  extra_args: string;
  env: EnvRow[];
  notes: string;
};

export const emptyForm: ProfileFormState = {
  name: "",
  executable_path: "",
  working_dir: "",
  model_path: "",
  alias: "",
  host: "0.0.0.0",
  port: "8080",
  ctx_size: "",
  n_gpu_layers: "",
  extra_args: "",
  env: [],
  notes: "",
};

export function formFromProfile(profile: Profile): ProfileFormState {
  return {
    name: profile.name,
    executable_path: profile.executable_path,
    working_dir: profile.working_dir ?? "",
    model_path: profile.model_path ?? "",
    alias: profile.alias ?? "",
    host: profile.host,
    port: String(profile.port),
    ctx_size: profile.ctx_size == null ? "" : String(profile.ctx_size),
    n_gpu_layers: profile.n_gpu_layers == null ? "" : String(profile.n_gpu_layers),
    extra_args: profile.extra_args.join("\n"),
    env: Object.entries(profile.env).map(([key, value]) => ({ key, value })),
    notes: profile.notes,
  };
}

function optionalInt(value: string): number | null {
  const text = value.trim();
  return text === "" ? null : Number(text);
}

export function payloadFromForm(form: ProfileFormState): ProfilePayload {
  const env: Record<string, string> = {};
  for (const row of form.env) {
    if (row.key.trim()) env[row.key.trim()] = row.value;
  }
  return {
    name: form.name,
    engine: "llama.cpp",
    executable_path: form.executable_path,
    working_dir: form.working_dir.trim() || null,
    model_path: form.model_path.trim() || null,
    alias: form.alias.trim() || null,
    host: form.host,
    port: Number(form.port),
    ctx_size: optionalInt(form.ctx_size),
    n_gpu_layers: optionalInt(form.n_gpu_layers),
    extra_args: form.extra_args.split("\n").filter((line) => line.trim() !== ""),
    env,
    notes: form.notes,
  };
}

export function validateForm(form: ProfileFormState): string | null {
  if (!form.name.trim()) return "Name is required";
  if (!form.executable_path.trim()) return "Executable path is required";
  const port = Number(form.port);
  if (!Number.isInteger(port) || port < 1 || port > 65535) return "Port must be 1 to 65535";
  for (const [label, value] of [
    ["Context size", form.ctx_size],
    ["GPU layers", form.n_gpu_layers],
  ]) {
    if (value.trim() !== "" && !Number.isInteger(Number(value))) {
      return `${label} must be a whole number`;
    }
  }
  return null;
}
