import { useEffect, useId, useRef, useState } from "react";

import { classNames } from "../lib/classNames";

export type SelectOption = { value: string; label: string };

/** A dropdown drawn by the page: the browser's own select popup does not follow the theme. */
export function Select({
  label,
  value,
  options,
  onChange,
  mono = false,
}: {
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  mono?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const labelId = useId();
  const text = mono ? "font-mono text-xs" : "text-sm";

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <div
      className="form-control relative"
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.stopPropagation();
          setOpen(false);
        }
      }}
      ref={root}
    >
      <span className="label-text" id={labelId}>
        {label}
      </span>
      <button
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-labelledby={labelId}
        className={classNames("select select-bordered select-sm items-center text-left", text)}
        onClick={() => setOpen(!open)}
        type="button"
      >
        <span className="truncate">
          {options.find((option) => option.value === value)?.label ?? value}
        </span>
      </button>
      {open ? (
        <div
          aria-labelledby={labelId}
          className="absolute left-0 right-0 top-full z-20 mt-1 max-h-60 overflow-y-auto rounded-md border border-zinc-700 bg-zinc-900 py-1 shadow-xl"
          role="listbox"
        >
          {options.map((option) => (
            <button
              aria-selected={option.value === value}
              className={classNames(
                "block w-full truncate px-3 py-1.5 text-left hover:bg-zinc-800/60",
                text,
                option.value === value ? "bg-primary/10 text-primary" : "text-zinc-300",
              )}
              key={option.value}
              onClick={() => {
                onChange(option.value);
                setOpen(false);
              }}
              role="option"
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
