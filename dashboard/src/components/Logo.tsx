/** App mark: a terminal window with a prompt. Mirrors public/favicon.svg. */
export function Logo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="#121214" />
      <rect x="12" y="14" width="40" height="36" rx="5" stroke="#d4d4d8" strokeWidth="3.5" />
      <path
        d="M21 26l8 6-8 6"
        stroke="#10b981"
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M34 39h9" stroke="#f59e0b" strokeWidth="4.5" strokeLinecap="round" />
    </svg>
  );
}
