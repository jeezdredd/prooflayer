import clsx from "clsx";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import client from "../api/client";
import { currentLang, locale, msg, t } from "../i18n";
import { useAuthStore } from "../stores/authStore";

interface Entry {
  slug: string;
  date: string;
  kind: "feature" | "improvement" | "fix";
  title_en: string;
  title_ru: string;
  body_en: string;
  body_ru: string;
}

const KIND: Record<Entry["kind"], { label: string; tone: string; dot: string }> = {
  feature: { label: msg("New"), tone: "text-signal-violet border-signal-violet/40 bg-signal-violet/10", dot: "bg-signal-violet" },
  improvement: { label: msg("Improved"), tone: "text-signal-cyan border-signal-cyan/40 bg-signal-cyan/10", dot: "bg-signal-cyan" },
  fix: { label: msg("Fixed"), tone: "text-signal-sage border-signal-sage/40 bg-signal-sage/10", dot: "bg-signal-sage" },
};

function formatDay(date: string): string {
  return new Date(`${date}T12:00:00`).toLocaleDateString(locale(), { day: "numeric", month: "long", year: "numeric" });
}

export default function ChangelogPage() {
  const user = useAuthStore((s) => s.user);
  const ru = currentLang() === "ru";
  const { data, isLoading, isError } = useQuery<{ entries: Entry[] }>({
    queryKey: ["changelog"],
    queryFn: () => client.get("/system/changelog/").then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });

  const days: { date: string; entries: Entry[] }[] = [];
  for (const entry of data?.entries ?? []) {
    const last = days[days.length - 1];
    if (last && last.date === entry.date) last.entries.push(entry);
    else days.push({ date: entry.date, entries: [entry] });
  }

  return (
    <div className="max-w-3xl">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <div className="label-mono flex items-center gap-2 mb-3">
          <span className="w-1.5 h-1.5 bg-signal-violet rounded-full pulse-dot" />
          {t("Changelog")}
        </div>
        <h1 className="font-display text-5xl lg:text-6xl text-ink-50 leading-none">
          {t("What's")} <span className="italic text-iris">{t("new")}</span>
        </h1>
        <p className="text-ink-300 mt-4 max-w-xl leading-relaxed">
          {t("Every change worth knowing about, the day it ships. A short digest of these also goes out by email.")}{" "}
          {user ? (
            <Link to="/account" className="text-signal-amber hover:underline">{t("Email settings")}</Link>
          ) : (
            <Link to="/register" className="text-signal-amber hover:underline">{t("Create an account to get it")}</Link>
          )}
        </p>
      </motion.div>

      {isLoading && <div className="mt-12 font-mono text-[11px] text-ink-500">{t("Loading…")}</div>}
      {isError && <div className="mt-12 font-mono text-[11px] text-signal-blood">{t("Could not load the changelog.")}</div>}

      <div className="mt-12 relative">
        <div className="absolute left-[7px] top-2 bottom-2 w-px bg-gradient-to-b from-signal-violet/40 via-white/10 to-transparent hidden sm:block" />
        <div className="space-y-12">
          {days.map((day, dIdx) => (
            <motion.section
              key={day.date}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: Math.min(dIdx * 0.06, 0.4) }}
              className="sm:pl-10 relative"
            >
              <span className="hidden sm:block absolute left-0 top-1.5 w-[15px] h-[15px] rounded-full border border-signal-violet/50 bg-ink-950">
                <span className="absolute inset-[4px] rounded-full bg-signal-violet" />
              </span>
              <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-400 mb-5">{formatDay(day.date)}</div>
              <div className="space-y-4">
                {day.entries.map((entry) => {
                  const kind = KIND[entry.kind] ?? KIND.feature;
                  const body = ru ? entry.body_ru : entry.body_en;
                  return (
                    <article key={entry.slug} className="case-card px-6 py-5">
                      <span className={clsx("inline-flex items-center gap-2 rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.16em]", kind.tone)}>
                        <span className={clsx("w-1.5 h-1.5 rounded-full", kind.dot)} />
                        {t(kind.label)}
                      </span>
                      <h2 className="font-display text-2xl text-ink-50 leading-tight mt-3">{ru ? entry.title_ru : entry.title_en}</h2>
                      {body && <p className="text-sm text-ink-300 leading-relaxed mt-2">{body}</p>}
                    </article>
                  );
                })}
              </div>
            </motion.section>
          ))}
        </div>
      </div>
    </div>
  );
}
