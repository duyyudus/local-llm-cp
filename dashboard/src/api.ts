export function defaultApiBaseUrl(protocol: string, hostname: string, port: string): string {
  return `${protocol}//${hostname || "localhost"}:${port}`;
}

// Without an explicit base URL the API is assumed to be on the host that served the
// dashboard, so the same build works from any machine on the network.
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  defaultApiBaseUrl(
    window.location.protocol,
    window.location.hostname,
    import.meta.env.VITE_API_PORT || "8040",
  );

export type ListEnvelope<T> = {
  items: T[];
  total: number;
};

export type RunState = "stopped" | "starting" | "ready" | "running" | "exited" | "unknown";

export type RunStatus = {
  status: RunState;
  pid: number | null;
  started_at: string | null;
  stopped_at: string | null;
  command_changed: boolean;
};

export type ProfilePayload = {
  name: string;
  engine: string;
  executable_path: string;
  working_dir: string | null;
  model_path: string | null;
  alias: string | null;
  host: string;
  port: number;
  ctx_size: number | null;
  n_gpu_layers: number | null;
  extra_args: string[];
  env: Record<string, string>;
  notes: string;
};

export type Profile = ProfilePayload & {
  id: string;
  command: string;
  run: RunStatus;
  created_at: string;
  updated_at: string;
};

export type ImportConflict = "skip" | "rename" | "overwrite";

export type ProfileExport = {
  format: string;
  version: number;
  exported_at: string | null;
  profiles: ProfilePayload[];
};

export type ImportResult = { created: string[]; updated: string[]; skipped: string[] };

export type CommandPreview = { command: string; argv: string[] };

export type HostInfo = {
  mode: string;
  target: string;
  connected: boolean;
  error: string | null;
  gpu_error: string | null;
};

export type DirEntry = { name: string; is_dir: boolean; size: number | null };

export type DirListing = { path: string; parent: string | null; entries: DirEntry[] };

export type GpuProcess = {
  pid: number;
  used_mb: number | null;
  profile_id: string | null;
  profile_name: string | null;
};

export type Gpu = {
  index: number;
  uuid: string;
  name: string;
  memory_used_mb: number | null;
  memory_total_mb: number | null;
  utilization_pct: number | null;
  temperature_c: number | null;
  power_w: number | null;
  processes: GpuProcess[];
};

export type GpuSnapshot = { ts: number; gpus: Gpu[] };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    throw new Error(await errorDetail(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function errorDetail(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const detail = (JSON.parse(text) as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      // FastAPI validation errors: [{loc: ["body", "port"], msg: "..."}]
      return detail
        .map((item: { loc?: unknown[]; msg?: string }) =>
          [item.loc?.slice(1).join("."), item.msg].filter(Boolean).join(": "),
        )
        .join("; ");
    }
  } catch {
    // Not JSON; fall through to the raw body.
  }
  return `${response.status} ${response.statusText}${text ? `: ${text}` : ""}`;
}

export const api = {
  host: () => request<HostInfo>("/host"),
  browse: (path: string) =>
    request<DirListing>(`/host/browse?path=${encodeURIComponent(path)}`),
  profiles: () => request<ListEnvelope<Profile>>("/profiles"),
  createProfile: (payload: ProfilePayload) =>
    request<Profile>("/profiles", { method: "POST", body: JSON.stringify(payload) }),
  updateProfile: (id: string, payload: ProfilePayload) =>
    request<Profile>(`/profiles/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteProfile: (id: string) => request<void>(`/profiles/${id}`, { method: "DELETE" }),
  duplicateProfile: (id: string) =>
    request<Profile>(`/profiles/${id}/duplicate`, { method: "POST" }),
  exportProfiles: (ids: string[]) =>
    request<ProfileExport>(
      `/profiles/export?${ids.map((id) => `id=${encodeURIComponent(id)}`).join("&")}`,
    ),
  importProfiles: (document: ProfileExport, onConflict: ImportConflict) =>
    request<ImportResult>(`/profiles/import?on_conflict=${onConflict}`, {
      method: "POST",
      body: JSON.stringify(document),
    }),
  previewCommand: (payload: ProfilePayload, signal?: AbortSignal) =>
    request<CommandPreview>("/profiles/preview-command", {
      method: "POST",
      body: JSON.stringify(payload),
      signal,
    }),
  startProfile: (id: string) => request<Profile>(`/profiles/${id}/start`, { method: "POST" }),
  stopProfile: (id: string) => request<Profile>(`/profiles/${id}/stop`, { method: "POST" }),
};

export function logStreamUrl(profileId: string): string {
  return `${API_BASE_URL}/profiles/${profileId}/logs/stream`;
}

export function gpuStreamUrl(): string {
  return `${API_BASE_URL}/gpu/stream`;
}
