import clsx from "clsx";

export function Spinner({ size = 20, className }: { size?: number; className?: string }) {
  return (
    <div
      className={clsx("inline-block rounded-full border-2 border-gray-200 border-t-blue-600 animate-spin-slow", className)}
      style={{ width: size, height: size }}
      role="status"
      aria-label="Loading"
    />
  );
}

export function PageSpinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 animate-fade-in">
      <Spinner size={32} />
      {label && <div className="text-sm text-gray-500">{label}</div>}
    </div>
  );
}
