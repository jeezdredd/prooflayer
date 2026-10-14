import clsx from "clsx";
import { useId } from "react";
import { motion } from "motion/react";
import { Globe } from "lucide-react";
import { t, useLangStore, type Lang } from "../i18n";

const OPTIONS: { value: Lang; label: string }[] = [
  { value: "ru", label: "RU" },
  { value: "en", label: "EN" },
];

export default function LangSwitch({ className }: { className?: string }) {
  const { lang, setLang } = useLangStore();
  const id = useId();
  return (
    <div
      role="radiogroup"
      aria-label={t("Interface language")}
      className={clsx("inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] p-0.5 pl-2 backdrop-blur", className)}
    >
      <Globe size={12} strokeWidth={1.6} className="text-ink-500 shrink-0" />
      {OPTIONS.map((o) => {
        const active = lang === o.value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setLang(o.value)}
            className={clsx("relative px-2.5 py-1 rounded-full text-[11px] font-medium tracking-wide transition-colors", active ? "text-ink-950" : "text-ink-400 hover:text-ink-100")}
          >
            {active && (
              <motion.span
                layoutId={`lang-pill-${id}`}
                className="absolute inset-0 rounded-full bg-ink-100"
                transition={{ type: "spring", stiffness: 500, damping: 35 }}
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
