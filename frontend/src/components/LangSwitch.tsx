import clsx from "clsx";
import { useLangStore, type Lang } from "../i18n";

const OPTIONS: { value: Lang; label: string }[] = [
  { value: "ru", label: "RU" },
  { value: "en", label: "EN" },
];

export default function LangSwitch({ className }: { className?: string }) {
  const { lang, setLang } = useLangStore();
  return (
    <div className={clsx("flex items-center border border-[var(--line-strong)] font-mono text-[10px] tracking-[0.14em]", className)}>
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => setLang(o.value)}
          aria-pressed={lang === o.value}
          className={clsx("px-2 py-1 transition-colors", lang === o.value ? "bg-ink-100 text-ink-950" : "text-ink-400 hover:text-ink-100")}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
