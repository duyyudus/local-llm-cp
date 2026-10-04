import type { ImportResult, Profile, ProfileExport } from "../../api";

export const EXPORT_FORMAT = "llm-cp-profiles";

export function parseExport(text: string): ProfileExport {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("The file is not valid JSON");
  }
  const document = data as Partial<ProfileExport> | null;
  if (document?.format !== EXPORT_FORMAT || !Array.isArray(document.profiles)) {
    throw new Error("The file is not a profile export");
  }
  if (document.profiles.length === 0) {
    throw new Error("The file contains no profiles");
  }
  return document as ProfileExport;
}

export function exportFileName(profile: Profile | null, now = new Date()): string {
  if (!profile) return `llm-cp-profiles-${now.toISOString().slice(0, 10)}.json`;
  const slug = profile.name.replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
  return `llm-cp-profile-${slug || profile.id}.json`;
}

export function importSummary(result: ImportResult): string {
  const parts = [
    result.created.length ? `${result.created.length} created` : "",
    result.updated.length ? `${result.updated.length} overwritten` : "",
    result.skipped.length ? `${result.skipped.length} skipped` : "",
  ].filter(Boolean);
  return `Import finished: ${parts.join(", ") || "nothing to import"}.`;
}
