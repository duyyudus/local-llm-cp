export function errorMessage(value: unknown): string {
  return value instanceof Error ? value.message : "Request failed";
}

export function formatGiB(megabytes: number | null | undefined): string {
  if (megabytes == null) return "n/a";
  return (megabytes / 1024).toFixed(1);
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 10 || unit === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unit]}`;
}

export function baseName(path: string | null | undefined): string {
  if (!path) return "";
  return path.split("/").filter(Boolean).pop() ?? path;
}

export function formatUptime(startedAt: string | null, now: number): string {
  if (!startedAt) return "";
  const seconds = Math.max(0, Math.floor((now - new Date(startedAt).getTime()) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m`;
  return `${seconds}s`;
}
