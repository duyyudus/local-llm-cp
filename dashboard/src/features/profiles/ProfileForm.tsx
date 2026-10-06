import { FolderOpen, Plus, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../../api";
import { Select } from "../../components/Select";
import { errorMessage } from "../../lib/format";
import { PathPicker } from "./PathPicker";
import {
  COMFY_PATHS,
  COMFY_PREVIEW_METHODS,
  COMFY_SWITCHES,
  COMFY_VRAM_MODES,
  DEFAULT_UV,
  ENGINES,
  payloadFromForm,
  validateForm,
  withEngine,
  type ComfyFormState,
  type Engine,
  type ProfileFormState,
} from "./form";

type Picker = {
  title: string;
  directory: boolean;
  value: string;
  apply: (form: ProfileFormState, path: string) => ProfileFormState;
};

const EXTRA_ARGS_PLACEHOLDER: Record<Engine, string> = {
  "llama.cpp": "--flash-attn on\n--parallel 2\n--jinja",
  comfyui: "--cuda-device 0\n--use-pytorch-cross-attention\n--verbose DEBUG",
};

export function ProfileForm({
  form,
  isNew,
  saving,
  error,
  setForm,
  onSave,
  onCancel,
}: {
  form: ProfileFormState;
  isNew: boolean;
  saving: boolean;
  error: string | null;
  setForm: (value: ProfileFormState) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const [picker, setPicker] = useState<Picker | null>(null);
  const [preview, setPreview] = useState("");
  const [previewError, setPreviewError] = useState<string | null>(null);
  const invalid = validateForm(form);
  const comfyui = form.engine === "comfyui";

  function update<K extends keyof ProfileFormState>(key: K, value: ProfileFormState[K]) {
    setForm({ ...form, [key]: value });
  }

  function updateComfy<K extends keyof ComfyFormState>(key: K, value: ComfyFormState[K]) {
    setForm({ ...form, comfy: { ...form.comfy, [key]: value } });
  }

  // The backend owns quoting and flag names, so the preview comes from it.
  useEffect(() => {
    if (validateForm(form)) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      api
        .previewCommand(payloadFromForm(form), controller.signal)
        .then((result) => {
          setPreview(result.command);
          setPreviewError(null);
        })
        .catch((reason) => {
          if (!controller.signal.aborted) setPreviewError(errorMessage(reason));
        });
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [form]);

  const pathField = (
    label: string,
    placeholder: string,
    value: string,
    apply: Picker["apply"],
    pickerTitle: string,
    directory = false,
  ) => (
    <label className="form-control sm:col-span-2" key={label}>
      <span className="label-text">{label}</span>
      <div className="flex gap-2">
        <input
          className="input input-bordered input-sm min-w-0 flex-1 font-mono text-xs"
          onChange={(event) => setForm(apply(form, event.target.value))}
          placeholder={placeholder}
          value={value}
        />
        <button
          className="btn btn-sm btn-outline shrink-0"
          onClick={() => setPicker({ title: pickerTitle, directory, value, apply })}
          type="button"
        >
          <FolderOpen className="h-4 w-4" />
          Browse
        </button>
      </div>
    </label>
  );

  const hostAndPort = (
    <>
      <label className="form-control">
        <span className="label-text">Host</span>
        <input
          className="input input-bordered input-sm font-mono text-xs"
          onChange={(event) => update("host", event.target.value)}
          value={form.host}
        />
      </label>
      <label className="form-control">
        <span className="label-text">Port</span>
        <input
          className="input input-bordered input-sm font-mono text-xs"
          inputMode="numeric"
          onChange={(event) => update("port", event.target.value)}
          value={form.port}
        />
      </label>
    </>
  );

  const llamaFields = (
    <>
      {pathField(
        "Server executable",
        "/path/to/llama-server",
        form.executable_path,
        (current, path) => ({ ...current, executable_path: path }),
        "Choose the server executable",
      )}
      <label className="form-control sm:col-span-2">
        <span className="label-text">Working directory</span>
        <input
          className="input input-bordered input-sm font-mono text-xs"
          onChange={(event) => update("working_dir", event.target.value)}
          placeholder="folder of the server executable"
          value={form.working_dir}
        />
        <span className="mt-1 text-xs text-zinc-500">
          Relative paths in the arguments below are resolved from here.
        </span>
      </label>
      {pathField(
        "Model path",
        "/path/to/model.gguf",
        form.model_path,
        (current, path) => ({ ...current, model_path: path }),
        "Choose a model file",
      )}
      <label className="form-control sm:col-span-2">
        <span className="label-text">Alias</span>
        <input
          className="input input-bordered input-sm"
          onChange={(event) => update("alias", event.target.value)}
          placeholder="model name reported by the API"
          value={form.alias}
        />
      </label>
      {hostAndPort}
      <label className="form-control">
        <span className="label-text">Context size</span>
        <input
          className="input input-bordered input-sm font-mono text-xs"
          inputMode="numeric"
          onChange={(event) => update("ctx_size", event.target.value)}
          placeholder="model default"
          value={form.ctx_size}
        />
      </label>
      <label className="form-control">
        <span className="label-text">GPU layers</span>
        <input
          className="input input-bordered input-sm font-mono text-xs"
          inputMode="numeric"
          onChange={(event) => update("n_gpu_layers", event.target.value)}
          placeholder="llama.cpp default"
          value={form.n_gpu_layers}
        />
      </label>
    </>
  );

  const comfyFields = (
    <>
      {pathField(
        "ComfyUI directory",
        "/path/to/ComfyUI",
        form.working_dir,
        (current, path) => ({ ...current, working_dir: path }),
        "Choose the ComfyUI repository",
        true,
      )}
      <p className="-mt-2 text-xs text-zinc-500 sm:col-span-2">
        The repository that holds main.py. The server is started there with uv run, using the
        environment already installed in it.
      </p>
      {hostAndPort}
      <Select
        label="VRAM mode"
        mono
        onChange={(value) => updateComfy("vram_mode", value)}
        options={[
          { value: "", label: "automatic" },
          ...COMFY_VRAM_MODES.map((mode) => ({ value: mode, label: `--${mode}` })),
        ]}
        value={form.comfy.vram_mode}
      />
      <Select
        label="Preview method"
        mono
        onChange={(value) => updateComfy("preview_method", value)}
        options={[
          { value: "", label: "ComfyUI default" },
          ...COMFY_PREVIEW_METHODS.map((method) => ({ value: method, label: method })),
        ]}
        value={form.comfy.preview_method}
      />
      <label className="form-control">
        <span className="label-text">Reserved VRAM (GB)</span>
        <input
          className="input input-bordered input-sm font-mono text-xs"
          inputMode="decimal"
          onChange={(event) => updateComfy("reserve_vram", event.target.value)}
          placeholder="ComfyUI default"
          value={form.comfy.reserve_vram}
        />
      </label>
      <label className="form-control">
        <span className="label-text">uv executable</span>
        <input
          className="input input-bordered input-sm font-mono text-xs"
          onChange={(event) => update("executable_path", event.target.value)}
          placeholder={DEFAULT_UV}
          value={form.executable_path}
        />
      </label>
      {COMFY_PATHS.map(({ key, label, directory }) =>
        pathField(
          label,
          "ComfyUI default",
          form.comfy[key],
          (current, path) => ({ ...current, comfy: { ...current.comfy, [key]: path } }),
          `Choose the ${label.toLowerCase()}`,
          directory,
        ),
      )}
      <div className="grid gap-x-3 gap-y-1 sm:col-span-2 sm:grid-cols-2">
        {COMFY_SWITCHES.map(({ key, flag, hint }) => (
          <label className="flex cursor-pointer items-center gap-2 py-1" key={key} title={hint}>
            <input
              checked={form.comfy[key]}
              className="checkbox checkbox-sm"
              onChange={(event) => updateComfy(key, event.target.checked)}
              type="checkbox"
            />
            <span className="font-mono text-xs text-zinc-200">{flag}</span>
          </label>
        ))}
      </div>
    </>
  );

  return (
    <div className="fixed inset-0 z-30 flex justify-end" role="dialog" aria-label="Profile editor">
      <div className="absolute inset-0 bg-black/50" onClick={onCancel} />
      <form
        className="relative flex h-full w-full max-w-2xl flex-col border-l border-zinc-800 bg-zinc-900 shadow-2xl"
        onSubmit={(event) => {
          event.preventDefault();
          onSave();
        }}
      >
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-3">
          <h2 className="text-sm font-bold uppercase tracking-widest text-zinc-200">
            {isNew ? "New profile" : "Edit profile"}
          </h2>
          <button aria-label="Close" className="btn btn-sm btn-ghost" onClick={onCancel} type="button">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="form-control">
              <span className="label-text">Profile name</span>
              <input
                autoFocus
                className="input input-bordered input-sm"
                onChange={(event) => update("name", event.target.value)}
                value={form.name}
              />
            </label>
            <Select
              label="Engine"
              onChange={(value) => setForm(withEngine(form, value as Engine))}
              options={ENGINES}
              value={form.engine}
            />
            {comfyui ? comfyFields : llamaFields}
          </div>

          <label className="form-control">
            <span className="label-text">Extra arguments</span>
            <textarea
              className="textarea textarea-bordered h-32 font-mono text-xs leading-5"
              onChange={(event) => update("extra_args", event.target.value)}
              placeholder={EXTRA_ARGS_PLACEHOLDER[form.engine]}
              spellCheck={false}
              value={form.extra_args}
            />
            <span className="mt-1 text-xs text-zinc-500">
              One flag per line, as in a shell script. Trailing backslashes and # comments are
              ignored.
            </span>
          </label>

          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="label-text">Environment variables</span>
              <button
                className="btn btn-xs btn-ghost"
                onClick={() => update("env", [...form.env, { key: "", value: "" }])}
                type="button"
              >
                <Plus className="h-3.5 w-3.5" />
                Add variable
              </button>
            </div>
            {form.env.length === 0 ? (
              <p className="text-xs text-zinc-500">
                None. Use CUDA_VISIBLE_DEVICES to pin the server to specific GPUs.
              </p>
            ) : null}
            <div className="space-y-2">
              {form.env.map((row, index) => (
                <div className="flex gap-2" key={index}>
                  <input
                    aria-label="Variable name"
                    className="input input-bordered input-sm w-2/5 font-mono text-xs"
                    onChange={(event) =>
                      update(
                        "env",
                        form.env.map((item, i) =>
                          i === index ? { ...item, key: event.target.value } : item,
                        ),
                      )
                    }
                    placeholder="CUDA_VISIBLE_DEVICES"
                    value={row.key}
                  />
                  <input
                    aria-label="Variable value"
                    className="input input-bordered input-sm min-w-0 flex-1 font-mono text-xs"
                    onChange={(event) =>
                      update(
                        "env",
                        form.env.map((item, i) =>
                          i === index ? { ...item, value: event.target.value } : item,
                        ),
                      )
                    }
                    placeholder="0,1"
                    value={row.value}
                  />
                  <button
                    aria-label="Remove variable"
                    className="btn btn-sm btn-ghost"
                    onClick={() =>
                      update(
                        "env",
                        form.env.filter((_, i) => i !== index),
                      )
                    }
                    type="button"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <label className="form-control">
            <span className="label-text">Notes</span>
            <textarea
              className="textarea textarea-bordered h-16 text-sm"
              onChange={(event) => update("notes", event.target.value)}
              value={form.notes}
            />
          </label>

          <div>
            <span className="label-text">Command preview</span>
            <pre
              className="console-output mt-1 whitespace-pre-wrap break-all rounded-md border border-zinc-800 bg-zinc-950 p-3 text-zinc-300"
              data-testid="command-preview"
            >
              {invalid ? "Fill in the required fields to see the command." : preview}
            </pre>
            {previewError && !invalid ? (
              <p className="mt-1 text-xs text-error">{previewError}</p>
            ) : null}
          </div>
        </div>

        <div className="border-t border-zinc-800 px-5 py-3">
          {error ? <div className="alert alert-error mb-3 text-sm">{error}</div> : null}
          <div className="flex items-center justify-end gap-2">
            {invalid ? <span className="mr-auto text-xs text-zinc-500">{invalid}</span> : null}
            <button className="btn btn-sm btn-ghost" onClick={onCancel} type="button">
              Cancel
            </button>
            <button className="btn btn-sm btn-primary" disabled={saving || !!invalid} type="submit">
              {isNew ? "Create profile" : "Save changes"}
            </button>
          </div>
        </div>
      </form>

      {picker ? (
        <PathPicker
          directory={picker.directory}
          initialValue={picker.value}
          onCancel={() => setPicker(null)}
          onSelect={(path) => {
            setForm(picker.apply(form, path));
            setPicker(null);
          }}
          title={picker.title}
        />
      ) : null}
    </div>
  );
}
