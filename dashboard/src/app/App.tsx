import { Moon, Server, Sun, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, type HostInfo, type Profile } from "../api";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Logo } from "../components/Logo";
import { StatusBadge } from "../components/StatusBadge";
import { ConsolePanel } from "../features/console/ConsolePanel";
import { GpuPanel } from "../features/gpu/GpuPanel";
import { useGpuStream } from "../features/gpu/useGpuStream";
import { ProfileForm } from "../features/profiles/ProfileForm";
import { ProfileList } from "../features/profiles/ProfileList";
import {
  emptyForm,
  formFromProfile,
  payloadFromForm,
  type ProfileFormState,
} from "../features/profiles/form";
import { isActive } from "../features/profiles/status";
import { errorMessage } from "../lib/format";

const PROFILE_POLL_MS = 2500;
const HOST_POLL_MS = 5000;
const SIDEBAR_MIN = 320;
const SIDEBAR_MAX = 720;

type Confirm = { kind: "stop" | "delete"; profile: Profile };
type Editor = { id: string | null; form: ProfileFormState };

function storedNumber(key: string, fallback: number): number {
  const value = Number(localStorage.getItem(key));
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

export function App() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);
  const [host, setHost] = useState<HostInfo | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [theme, setTheme] = useState(() => localStorage.getItem("llm-cp-theme") ?? "dark");
  const [sidebarWidth, setSidebarWidth] = useState(() => storedNumber("llm-cp-sidebar", 420));
  const dragging = useRef(false);
  const gpuStream = useGpuStream();

  useEffect(() => {
    const dark = theme !== "light";
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.dataset.theme = dark ? "emerald_dark" : "emerald_light";
    localStorage.setItem("llm-cp-theme", theme);
  }, [theme]);

  const loadProfiles = useCallback(async () => {
    try {
      const result = await api.profiles();
      setProfiles(result.items);
      setApiError(null);
    } catch (reason) {
      setApiError(`Cannot reach the API: ${errorMessage(reason)}`);
    } finally {
      setLoading(false);
      setNow(Date.now());
    }
  }, []);

  useEffect(() => {
    void loadProfiles();
    const timer = window.setInterval(() => void loadProfiles(), PROFILE_POLL_MS);
    return () => window.clearInterval(timer);
  }, [loadProfiles]);

  useEffect(() => {
    const load = () =>
      api
        .host()
        .then(setHost)
        .catch(() => setHost(null));
    void load();
    const timer = window.setInterval(() => void load(), HOST_POLL_MS);
    return () => window.clearInterval(timer);
  }, []);

  // Show a console straight away when something is already running.
  useEffect(() => {
    if (selectedId && profiles.some((profile) => profile.id === selectedId)) return;
    const running = profiles.find((profile) => isActive(profile.run.status));
    setSelectedId(running?.id ?? null);
  }, [profiles, selectedId]);

  async function runAction(profile: Profile, action: () => Promise<unknown>) {
    setBusyId(profile.id);
    setActionError(null);
    try {
      await action();
    } catch (reason) {
      setActionError(`${profile.name}: ${errorMessage(reason)}`);
    } finally {
      setBusyId(null);
      await loadProfiles();
    }
  }

  function start(profile: Profile) {
    setSelectedId(profile.id);
    void runAction(profile, () => api.startProfile(profile.id));
  }

  function confirmed() {
    if (!confirm) return;
    const { kind, profile } = confirm;
    setConfirm(null);
    void runAction(profile, () =>
      kind === "stop" ? api.stopProfile(profile.id) : api.deleteProfile(profile.id),
    );
  }

  async function save() {
    if (!editor) return;
    setSaving(true);
    setEditorError(null);
    try {
      const payload = payloadFromForm(editor.form);
      if (editor.id) await api.updateProfile(editor.id, payload);
      else await api.createProfile(payload);
      setEditor(null);
      await loadProfiles();
    } catch (reason) {
      setEditorError(errorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  function openEditor(profile: Profile | null) {
    setEditorError(null);
    setEditor({ id: profile?.id ?? null, form: profile ? formFromProfile(profile) : emptyForm });
  }

  function startResize(event: React.PointerEvent<HTMLDivElement>) {
    dragging.current = true;
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function resize(event: React.PointerEvent<HTMLDivElement>) {
    if (!dragging.current) return;
    setSidebarWidth(Math.max(SIDEBAR_MIN, Math.min(SIDEBAR_MAX, event.clientX)));
  }

  function endResize() {
    dragging.current = false;
    localStorage.setItem("llm-cp-sidebar", String(sidebarWidth));
  }

  const selected = profiles.find((profile) => profile.id === selectedId) ?? null;
  const tabs = profiles.filter(
    (profile) => profile.id === selectedId || isActive(profile.run.status),
  );
  const runningCount = profiles.filter((profile) => isActive(profile.run.status)).length;

  return (
    <div
      className="flex min-h-screen flex-col bg-base-100 text-base-content lg:h-screen"
      data-testid="dashboard-root"
    >
      <header className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-zinc-800 bg-zinc-950 px-4 py-2">
        <div className="flex items-center gap-3">
          <Logo className="h-8 w-8 shrink-0" />
          <div>
            <h1 className="text-sm font-bold tracking-wide text-zinc-100">Local LLM</h1>
            <div className="text-xs font-semibold uppercase tracking-widest text-zinc-500">
              Control panel
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <span className="text-xs text-zinc-500">{runningCount} running</span>
          {host ? (
            <span title={host.error ?? undefined}>
              <StatusBadge tone={host.connected ? "success" : "error"}>
                <Server className="h-3 w-3" />
                {host.mode === "local" ? "local host" : host.target}
                {host.connected ? "" : " offline"}
              </StatusBadge>
            </span>
          ) : (
            <StatusBadge tone="error">API offline</StatusBadge>
          )}
          <button
            aria-label="Toggle colour theme"
            className="btn btn-sm btn-ghost"
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            type="button"
          >
            {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
          </button>
        </div>
      </header>

      {apiError || actionError || (host && !host.connected && host.error) ? (
        <div className="space-y-2 border-b border-zinc-800 bg-zinc-950 px-4 py-2">
          {apiError ? <div className="alert alert-error py-2 text-sm">{apiError}</div> : null}
          {host && !host.connected && host.error ? (
            <div className="alert alert-warning py-2 text-sm">{host.error}</div>
          ) : null}
          {actionError ? (
            <div className="alert alert-error flex justify-between py-2 text-sm" role="alert">
              <span>{actionError}</span>
              <button
                aria-label="Dismiss"
                className="btn btn-xs btn-ghost"
                onClick={() => setActionError(null)}
                type="button"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      <div
        className="flex min-h-0 flex-1 flex-col lg:flex-row"
        style={{ "--sidebar": `${sidebarWidth}px` } as React.CSSProperties}
      >
        <aside className="flex max-h-[50vh] shrink-0 flex-col overflow-hidden border-b border-zinc-800 bg-zinc-900/40 lg:max-h-none lg:w-[var(--sidebar)] lg:border-b-0">
          <ProfileList
            busyId={busyId}
            loading={loading}
            now={now}
            onCreate={() => openEditor(null)}
            onDelete={(profile) => setConfirm({ kind: "delete", profile })}
            onDuplicate={(profile) => void runAction(profile, () => api.duplicateProfile(profile.id))}
            onEdit={openEditor}
            onSelect={(profile) => setSelectedId(profile.id)}
            onStart={start}
            onStop={(profile) => setConfirm({ kind: "stop", profile })}
            profiles={profiles}
            selectedId={selectedId}
          />
        </aside>
        <div
          aria-label="Resize profile list"
          aria-orientation="vertical"
          className="hidden w-1 shrink-0 cursor-col-resize bg-zinc-800 transition-colors hover:bg-primary lg:block"
          onPointerDown={startResize}
          onPointerMove={resize}
          onPointerUp={endResize}
          role="separator"
        />
        <main className="flex min-h-0 min-w-0 flex-1 flex-col gap-3 p-3">
          <GpuPanel stream={gpuStream} />
          <ConsolePanel onSelect={(profile) => setSelectedId(profile.id)} selected={selected} tabs={tabs} />
        </main>
      </div>

      {editor ? (
        <ProfileForm
          error={editorError}
          form={editor.form}
          isNew={editor.id === null}
          onCancel={() => setEditor(null)}
          onSave={() => void save()}
          saving={saving}
          setForm={(form) => setEditor({ ...editor, form })}
        />
      ) : null}

      <ConfirmDialog
        confirmLabel={confirm?.kind === "stop" ? "Stop server" : "Delete profile"}
        description={
          confirm?.kind === "stop"
            ? "The server process is terminated and its model is unloaded from VRAM."
            : "The profile, its saved arguments and its log files on the GPU host are removed."
        }
        onCancel={() => setConfirm(null)}
        onConfirm={confirmed}
        open={confirm !== null}
        title={
          confirm ? `${confirm.kind === "stop" ? "Stop" : "Delete"} ${confirm.profile.name}?` : ""
        }
      />
    </div>
  );
}
