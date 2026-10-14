import { useState, type ReactNode } from "react";
import clsx from "clsx";
import { EyeOff } from "lucide-react";
import { t } from "../i18n";

interface SensitiveCoverProps {
  sensitive?: boolean;
  children: ReactNode;
  className?: string;
}

export default function SensitiveCover({ sensitive, children, className }: SensitiveCoverProps) {
  const [shown, setShown] = useState(false);
  if (!sensitive || shown) return <>{children}</>;
  return (
    <div className={clsx("relative overflow-hidden", className)}>
      <div className="w-full h-full blur-2xl scale-110 pointer-events-none select-none" aria-hidden="true">
        {children}
      </div>
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setShown(true);
        }}
        className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-ink-950/70 text-ink-100 font-mono text-[10px] uppercase tracking-[0.14em] hover:text-signal-amber transition-colors"
      >
        <EyeOff size={16} strokeWidth={1.5} />
        {t("Sensitive content, click to show")}
      </button>
    </div>
  );
}
