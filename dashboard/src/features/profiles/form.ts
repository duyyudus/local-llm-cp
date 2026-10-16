import type { EngineOptions, Profile, ProfilePayload } from "../../api";

export type EnvRow = { key: string; value: string };

export type Engine = "llama.cpp" | "comfyui" | "tabbyapi";

export const ENGINES: { value: Engine; label: string }[] = [
  { value: "llama.cpp", label: "llama.cpp" },
  { value: "comfyui", label: "ComfyUI" },
  { value: "tabbyapi", label: "tabbyAPI" },
];

// ComfyUI is started as `uv run main.py` inside its repository, so its executable is uv.
// An empty uv field in the form stands for this path.
export const DEFAULT_UV = "~/.local/bin/uv";

// tabbyAPI is started with the start.sh of its repository.
export const TABBY_LAUNCHER = "start.sh";

const DEFAULT_PORT: Record<Engine, string> = {
  "llama.cpp": "8080",
  comfyui: "8188",
  tabbyapi: "5000",
};

export const COMFY_VRAM_MODES = ["gpu-only", "highvram", "normalvram", "lowvram", "novram", "cpu"];
export const COMFY_PREVIEW_METHODS = ["none", "auto", "latent2rgb", "taesd"];

export const COMFY_SWITCHES = [
  { key: "fast", flag: "--fast", hint: "Turn on untested speed optimisations" },
  {
    key: "disable_smart_memory",
    flag: "--disable-smart-memory",
    hint: "Unload models to system RAM eagerly instead of keeping them in VRAM",
  },
  {
    key: "enable_cors_header",
    flag: "--enable-cors-header",
    hint: "Allow requests from other origins",
  },
  { key: "multi_user", flag: "--multi-user", hint: "Keep settings and workflows per user" },
  {
    key: "disable_all_custom_nodes",
    flag: "--disable-all-custom-nodes",
    hint: "Load the core nodes only",
  },
  { key: "enable_manager", flag: "--enable-manager", hint: "Turn on ComfyUI-Manager" },
] as const;

export type ComfySwitch = (typeof COMFY_SWITCHES)[number]["key"];

export const COMFY_PATHS = [
  { key: "output_directory", label: "Output directory", directory: true },
  { key: "input_directory", label: "Input directory", directory: true },
  { key: "extra_model_paths_config", label: "Extra model paths config", directory: false },
] as const;

export type ComfyPath = (typeof COMFY_PATHS)[number]["key"];

export type ComfyFormState = Record<ComfySwitch, boolean> &
  Record<ComfyPath, string> & {
    vram_mode: string;
    preview_method: string;
    reserve_vram: string;
  };

export type TabbyFormState = {
  config: string;
  model_name: string;
  max_seq_len: string;
  gpu_split: string;
};

export type ProfileFormState = {
  name: string;
  engine: Engine;
  executable_path: string;
  working_dir: string;
  model_path: string;
  alias: string;
  host: string;
  port: string;
  ctx_size: string;
  n_gpu_layers: string;
  comfy: ComfyFormState;
  tabby: TabbyFormState;
  extra_args: string;
  env: EnvRow[];
  notes: string;
};

const emptyTabby: TabbyFormState = { config: "", model_name: "", max_seq_len: "", gpu_split: "" };

const emptyComfy: ComfyFormState = {
  vram_mode: "",
  preview_method: "",
  reserve_vram: "",
  output_directory: "",
  input_directory: "",
  extra_model_paths_config: "",
  fast: false,
  disable_smart_memory: false,
  enable_cors_header: false,
  multi_user: false,
  disable_all_custom_nodes: false,
  enable_manager: false,
};

export const emptyForm: ProfileFormState = {
  name: "",
  engine: "llama.cpp",
  executable_path: "",
  working_dir: "",
  model_path: "",
  alias: "",
  host: "0.0.0.0",
  port: "8080",
  ctx_size: "",
  n_gpu_layers: "",
  comfy: emptyComfy,
  tabby: emptyTabby,
  extra_args: "",
  env: [],
  notes: "",
};

/** Switch engine, replacing the launch target and a port still at the old engine's default. */
export function withEngine(form: ProfileFormState, engine: Engine): ProfileFormState {
  if (engine === form.engine) return form;
  const untouched = form.port === DEFAULT_PORT[form.engine];
  if (engine === "tabbyapi") {
    // Left empty, these are filled in from the repository's config once it is chosen.
    return {
      ...form,
      engine,
      executable_path: "",
      working_dir: "",
      host: form.host === emptyForm.host ? "" : form.host,
      port: untouched ? "" : form.port,
    };
  }
  return {
    ...form,
    engine,
    executable_path: "",
    working_dir: "",
    host: form.host || emptyForm.host,
    port: untouched || !form.port ? DEFAULT_PORT[engine] : form.port,
  };
}

/** Sizes in GB, separated by commas or spaces; null when one is not a number. */
export function parseGpuSplit(text: string): number[] | null {
  const parts = text.split(/[\s,]+/).filter(Boolean);
  const sizes = parts.map(Number);
  return sizes.every((size) => Number.isFinite(size) && size >= 0) ? sizes : null;
}

function tabbyFromOptions(options: EngineOptions): TabbyFormState {
  const value = (key: string) => (options[key] == null ? "" : String(options[key]));
  const split = options.gpu_split;
  return {
    config: value("config"),
    model_name: value("model_name"),
    max_seq_len: value("max_seq_len"),
    gpu_split: Array.isArray(split) ? split.join(", ") : "",
  };
}

function optionsFromTabby(tabby: TabbyFormState): EngineOptions {
  const options: EngineOptions = {};
  if (tabby.config.trim()) options.config = tabby.config.trim();
  if (tabby.model_name.trim()) options.model_name = tabby.model_name.trim();
  if (tabby.max_seq_len.trim()) options.max_seq_len = Number(tabby.max_seq_len);
  const split = parseGpuSplit(tabby.gpu_split);
  if (split?.length) options.gpu_split = split;
  return options;
}

function comfyFromOptions(options: EngineOptions): ComfyFormState {
  const comfy = { ...emptyComfy };
  for (const key of ["vram_mode", "preview_method", "reserve_vram"] as const) {
    if (options[key] != null) comfy[key] = String(options[key]);
  }
  for (const { key } of COMFY_PATHS) {
    if (options[key] != null) comfy[key] = String(options[key]);
  }
  for (const { key } of COMFY_SWITCHES) comfy[key] = options[key] === true;
  return comfy;
}

function optionsFromComfy(comfy: ComfyFormState): EngineOptions {
  const options: EngineOptions = {};
  if (comfy.vram_mode) options.vram_mode = comfy.vram_mode;
  if (comfy.preview_method) options.preview_method = comfy.preview_method;
  if (comfy.reserve_vram.trim()) options.reserve_vram = Number(comfy.reserve_vram);
  for (const { key } of COMFY_PATHS) {
    if (comfy[key].trim()) options[key] = comfy[key].trim();
  }
  for (const { key } of COMFY_SWITCHES) {
    if (comfy[key]) options[key] = true;
  }
  return options;
}

function engineOf(name: string): Engine {
  return ENGINES.find((engine) => engine.value === name)?.value ?? "llama.cpp";
}

export function formFromProfile(profile: Profile): ProfileFormState {
  const engine = engineOf(profile.engine);
  const comfyui = engine === "comfyui";
  const options = profile.engine_options ?? {};
  return {
    name: profile.name,
    engine,
    executable_path:
      comfyui && profile.executable_path === DEFAULT_UV ? "" : profile.executable_path,
    working_dir: profile.working_dir ?? "",
    model_path: profile.model_path ?? "",
    alias: profile.alias ?? "",
    host: profile.host,
    port: String(profile.port),
    ctx_size: profile.ctx_size == null ? "" : String(profile.ctx_size),
    n_gpu_layers: profile.n_gpu_layers == null ? "" : String(profile.n_gpu_layers),
    comfy: comfyui ? comfyFromOptions(options) : emptyComfy,
    tabby: engine === "tabbyapi" ? tabbyFromOptions(options) : emptyTabby,
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
  // Each engine only sends its own settings; the other engine's fields stay in the form.
  const llama = form.engine === "llama.cpp";
  const executable = {
    "llama.cpp": form.executable_path,
    comfyui: form.executable_path.trim() || DEFAULT_UV,
    tabbyapi: form.executable_path.trim() || TABBY_LAUNCHER,
  }[form.engine];
  const engineOptions: EngineOptions = {
    "llama.cpp": {},
    comfyui: optionsFromComfy(form.comfy),
    tabbyapi: optionsFromTabby(form.tabby),
  }[form.engine];
  return {
    name: form.name,
    engine: form.engine,
    executable_path: executable,
    working_dir: form.working_dir.trim() || null,
    model_path: llama ? form.model_path.trim() || null : null,
    alias: llama ? form.alias.trim() || null : null,
    host: form.host,
    port: Number(form.port),
    ctx_size: llama ? optionalInt(form.ctx_size) : null,
    n_gpu_layers: llama ? optionalInt(form.n_gpu_layers) : null,
    engine_options: engineOptions,
    extra_args: form.extra_args.split("\n").filter((line) => line.trim() !== ""),
    env,
    notes: form.notes,
  };
}

export function validateForm(form: ProfileFormState): string | null {
  if (!form.name.trim()) return "Name is required";
  if (form.engine === "comfyui") {
    if (!form.working_dir.trim()) return "ComfyUI directory is required";
  } else if (form.engine === "tabbyapi") {
    if (!form.working_dir.trim()) return "tabbyAPI directory is required";
  } else if (!form.executable_path.trim()) {
    return "Executable path is required";
  }
  if (form.engine === "tabbyapi" && !form.port.trim()) {
    return "Port is required; press Tab in it to use the config's";
  }
  const port = Number(form.port);
  if (!Number.isInteger(port) || port < 1 || port > 65535) return "Port must be 1 to 65535";
  if (form.engine === "comfyui") {
    const reserve = form.comfy.reserve_vram.trim();
    if (reserve !== "" && !(Number(reserve) >= 0)) return "Reserved VRAM must be a number of GB";
    return null;
  }
  if (form.engine === "tabbyapi") {
    const seqLen = form.tabby.max_seq_len.trim();
    if (seqLen !== "" && !(Number.isInteger(Number(seqLen)) && Number(seqLen) >= -1)) {
      return "Max sequence length must be a whole number, or -1 for the model's own";
    }
    if (parseGpuSplit(form.tabby.gpu_split) === null) return "GPU split must be sizes in GB";
    return null;
  }
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
