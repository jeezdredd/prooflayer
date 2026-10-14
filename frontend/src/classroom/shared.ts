import type { Classroom } from "../types";
import { t } from "../i18n";

export const MAIN_URL: string = import.meta.env.VITE_MAIN_URL || "https://prooflayer.cloud";

export const INPUT = "flex-1 min-w-0 bg-transparent border border-[var(--line-strong)] px-3 py-2 text-ink-50 focus:border-signal-amber outline-none";
export const ACTION = "border border-signal-amber/60 text-signal-amber px-4 font-mono text-[11px] uppercase tracking-[0.14em] hover:bg-signal-amber/10 disabled:opacity-40";
export const SECTION_LABEL = "font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-2";

export function classPath(c: Pick<Classroom, "id" | "organization_slug">): string {
  return c.organization_slug ? `/${c.organization_slug}/c/${c.id}` : `/c/${c.id}`;
}

export function errorText(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: Record<string, unknown> } })?.response?.data;
  if (!data) return fallback;
  if (typeof data.detail === "string") return t(data.detail);
  const first = Object.values(data)[0];
  if (Array.isArray(first)) return t(String(first[0]));
  return fallback;
}

export function levelOptions(): { value: number; label: string }[] {
  return [
    ...Array.from({ length: 11 }, (_, i) => ({ value: i + 1, label: t("Grade {n}", { n: i + 1 }) })),
    ...Array.from({ length: 6 }, (_, i) => ({ value: 12 + i, label: t("University year {n}", { n: i + 1 }) })),
  ];
}

export function levelLabel(level: number | null | undefined): string {
  return levelOptions().find((o) => o.value === level)?.label ?? t("Year not set");
}
