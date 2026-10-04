import { Copy, Pencil, Play, Plus, Square, Trash2 } from "lucide-react";

import type { Profile } from "../../api";
import { classNames } from "../../lib/classNames";
import { baseName, formatUptime } from "../../lib/format";
import { RunStatusBadge, isActive } from "./status";

export function ProfileList({
  profiles,
  loading,
  selectedId,
  busyId,
  now,
  onSelect,
  onCreate,
  onEdit,
  onDuplicate,
  onDelete,
  onStart,
  onStop,
}: {
  profiles: Profile[];
  loading: boolean;
  selectedId: string | null;
  busyId: string | null;
  now: number;
  onSelect: (profile: Profile) => void;
  onCreate: () => void;
  onEdit: (profile: Profile) => void;
  onDuplicate: (profile: Profile) => void;
  onDelete: (profile: Profile) => void;
  onStart: (profile: Profile) => void;
  onStop: (profile: Profile) => void;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-zinc-800/60 px-4 py-3">
        <h2 className="text-sm font-bold uppercase tracking-widest text-zinc-200">
          Profiles <span className="font-normal text-zinc-500">{profiles.length}</span>
        </h2>
        <button className="btn btn-sm btn-primary" onClick={onCreate} type="button">
          <Plus className="h-4 w-4" />
          New profile
        </button>
      </div>
      <ul className="min-h-0 flex-1 overflow-y-auto">
        {profiles.length === 0 ? (
          <li className="px-4 py-10 text-center text-sm text-zinc-500">
            {loading
              ? "Loading profiles"
              : "No profiles yet. Create one to replace a launch script."}
          </li>
        ) : null}
        {profiles.map((profile) => {
          const active = isActive(profile.run.status);
          const busy = busyId === profile.id;
          return (
            <li
              className={classNames(
                "group border-b border-zinc-800/60 border-l-[3px] px-4 py-3 transition-colors",
                selectedId === profile.id
                  ? "border-l-primary bg-primary/10"
                  : "border-l-transparent hover:bg-zinc-800/30",
              )}
              key={profile.id}
            >
              <div className="flex items-start gap-3">
                <button
                  className="min-w-0 flex-1 text-left"
                  onClick={() => onSelect(profile)}
                  title={profile.command}
                  type="button"
                >
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold text-zinc-100">
                      {profile.name}
                    </span>
                    <RunStatusBadge status={profile.run.status} />
                  </div>
                  <div className="mt-1 truncate font-mono text-xs text-zinc-400">
                    {baseName(profile.model_path) || baseName(profile.executable_path)}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-zinc-500">
                    <span className="font-mono">
                      {profile.host}:{profile.port}
                    </span>
                    {profile.alias ? <span>alias {profile.alias}</span> : null}
                    {profile.ctx_size != null ? <span>ctx {profile.ctx_size}</span> : null}
                    {profile.env.CUDA_VISIBLE_DEVICES ? (
                      <span>gpu {profile.env.CUDA_VISIBLE_DEVICES}</span>
                    ) : null}
                    {active && profile.run.pid ? (
                      <span>
                        pid {profile.run.pid}, up {formatUptime(profile.run.started_at, now)}
                      </span>
                    ) : null}
                  </div>
                  {active && profile.run.command_changed ? (
                    <div className="mt-1 text-xs text-warning">
                      Edited since launch. Restart to apply.
                    </div>
                  ) : null}
                </button>
                {active ? (
                  <button
                    className="btn btn-sm btn-outline btn-error shrink-0"
                    disabled={busy}
                    onClick={() => onStop(profile)}
                    type="button"
                  >
                    <Square className="h-3.5 w-3.5" />
                    Stop
                  </button>
                ) : (
                  <button
                    className="btn btn-sm btn-outline btn-primary shrink-0"
                    disabled={busy}
                    onClick={() => onStart(profile)}
                    type="button"
                  >
                    <Play className="h-3.5 w-3.5" />
                    Start
                  </button>
                )}
              </div>
              <div className="mt-2 flex gap-1">
                <button className="btn btn-xs btn-ghost" onClick={() => onEdit(profile)} type="button">
                  <Pencil className="h-3.5 w-3.5" />
                  Edit
                </button>
                <button
                  className="btn btn-xs btn-ghost"
                  onClick={() => onDuplicate(profile)}
                  type="button"
                >
                  <Copy className="h-3.5 w-3.5" />
                  Duplicate
                </button>
                <button
                  className="btn btn-xs btn-ghost text-error"
                  disabled={active}
                  onClick={() => onDelete(profile)}
                  title={active ? "Stop the profile before deleting it" : undefined}
                  type="button"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
