import type { ClassAttention } from "../types";
import { t, tn } from "../i18n";
import { INPUT } from "./shared";

export function AttentionLine({ attention }: { attention?: ClassAttention | null }) {
  if (!attention) return null;
  const parts: { text: string; tone: string }[] = [];
  if (attention.open_objections > 0) {
    const late = attention.overdue_objections > 0 ? ` ${t("({n} overdue)", { n: attention.overdue_objections })}` : "";
    parts.push({
      text: tn(attention.open_objections, "{n} objection waiting for an answer", "{n} objections waiting for an answer") + late,
      tone: attention.overdue_objections > 0 ? "text-signal-blood" : "text-signal-amber",
    });
  }
  if (attention.needs_attention > 0) {
    parts.push({ text: tn(attention.needs_attention, "{n} flagged work", "{n} flagged works"), tone: "text-signal-amber" });
  }
  if (parts.length === 0) return <span className="block text-[11px] text-ink-600">{t("Nothing needs attention")}</span>;
  return (
    <span className="block text-[11px]">
      {parts.map((p, i) => (
        <span key={p.text} className={p.tone}>{i > 0 && <span className="text-ink-600"> · </span>}{p.text}</span>
      ))}
    </span>
  );
}

export function NameField({ value, onChange, teacher = false }: { value: string; onChange: (value: string) => void; teacher?: boolean }) {
  return (
    <label className="block mb-3">
      <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("First and last name")}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        maxLength={120}
        autoComplete="name"
        placeholder={t("For example, Anna Kovaleva")}
        className={`${INPUT} w-full mt-2`}
      />
      <span className="block text-xs text-ink-500 mt-1">
        {teacher ? t("Students and colleagues will see this name instead of your login.") : t("Your teacher will see this name next to your work.")}
      </span>
    </label>
  );
}
