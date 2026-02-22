interface StatusBadgeProps {
  status: string;
  label?: string;
}

const colorMap: Record<string, { bg: string; text: string; dot: string }> = {
  ok: { bg: 'rgba(16,185,129,0.12)', text: 'var(--accent-green)', dot: 'var(--accent-green)' },
  error: { bg: 'rgba(239,68,68,0.12)', text: 'var(--accent-red)', dot: 'var(--accent-red)' },
  unreachable: { bg: 'rgba(234,179,8,0.12)', text: 'var(--accent-yellow)', dot: 'var(--accent-yellow)' },
  running: { bg: 'rgba(59,130,246,0.12)', text: 'var(--accent-blue)', dot: 'var(--accent-blue)' },
  completed: { bg: 'rgba(16,185,129,0.12)', text: 'var(--accent-green)', dot: 'var(--accent-green)' },
  failed: { bg: 'rgba(239,68,68,0.12)', text: 'var(--accent-red)', dot: 'var(--accent-red)' },
};

export default function StatusBadge({ status, label }: StatusBadgeProps) {
  const colors = colorMap[status] || colorMap['error'];
  return (
    <span
      className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium gap-1.5"
      style={{ background: colors.bg, color: colors.text }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full status-dot"
        style={{ background: colors.dot }}
      />
      {label || status.toUpperCase()}
    </span>
  );
}
