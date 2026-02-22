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

export default function Skeleton({ className = '', rows = 3 }: SkeletonProps) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonLine key={i} className={i === 0 ? 'w-3/4' : i === rows - 1 ? 'w-1/2' : 'w-full'} />
      ))}
    </div>
  );
}
