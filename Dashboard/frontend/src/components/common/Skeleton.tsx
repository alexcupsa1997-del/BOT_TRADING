interface SkeletonProps {
  className?: string;
  rows?: number;
}

export function SkeletonLine({ className = '' }: { className?: string }) {
  return <div className={`skeleton h-4 ${className}`} />;
}

export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`glass-card p-4 space-y-3 ${className}`}>
      <SkeletonLine className="w-24 h-3" />
      <SkeletonLine className="w-32 h-7" />
      <SkeletonLine className="w-16 h-3" />
    </div>
  );
}

export function SkeletonChart({ className = '' }: { className?: string }) {
  return (
    <div className={`glass-card p-4 space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <SkeletonLine className="w-32 h-4" />
        <SkeletonLine className="w-20 h-4" />
      </div>
      <div className="skeleton h-48 rounded-lg" />
    </div>
  );
}

export function SkeletonTable({ rows = 5, className = '' }: { rows?: number; className?: string }) {
  return (
    <div className={`glass-card overflow-hidden ${className}`}>
      <div className="p-4 border-b border-[var(--border-color)]">
        <SkeletonLine className="w-36 h-5" />
      </div>
      <div className="p-4 space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <SkeletonLine className="w-16 h-4" />
            <SkeletonLine className="flex-1 h-4" />
            <SkeletonLine className="w-20 h-4" />
            <SkeletonLine className="w-16 h-4" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function SkeletonKPI() {
  return (
    <div className="glass-card p-4 space-y-2">
      <div className="flex items-center gap-2">
        <div className="skeleton w-8 h-8 rounded-lg" />
        <SkeletonLine className="w-20 h-3" />
      </div>
      <SkeletonLine className="w-24 h-7" />
      <SkeletonLine className="w-16 h-3" />
    </div>
  );
}

export default function Skeleton({ className = '', rows = 3 }: SkeletonProps) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonLine key={i} className={i === 0 ? 'w-3/4' : i === rows - 1 ? 'w-1/2' : 'w-full'} />
      ))}
    </div>
  );
}
