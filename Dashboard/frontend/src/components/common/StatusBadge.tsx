interface StatusBadgeProps {
  status: string;
  label?: string;
}

const colorMap: Record<string, string> = {
  ok: 'bg-[var(--accent-green)]/15 text-[var(--accent-green)] border-[var(--accent-green)]/30',
  error: 'bg-[var(--accent-red)]/15 text-[var(--accent-red)] border-[var(--accent-red)]/30',
  unreachable: 'bg-[var(--accent-yellow)]/15 text-[var(--accent-yellow)] border-[var(--accent-yellow)]/30',
  running: 'bg-[var(--accent-blue)]/15 text-[var(--accent-blue)] border-[var(--accent-blue)]/30',
  completed: 'bg-[var(--accent-green)]/15 text-[var(--accent-green)] border-[var(--accent-green)]/30',
  failed: 'bg-[var(--accent-red)]/15 text-[var(--accent-red)] border-[var(--accent-red)]/30',
};

export default function StatusBadge({ status, label }: StatusBadgeProps) {
  const classes = colorMap[status] || colorMap['error'];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${classes}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5" />
      {label || status.toUpperCase()}
    </span>
  );
}
