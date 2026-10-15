import { useState } from "react";
import { motion } from "motion/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import client from "../../api/client";
import { useAuthStore } from "../../stores/authStore";
import { toast } from "../ui/Toast";
import { currentLang, msg, t } from "../../i18n";

type Status = "exploring" | "building" | "beta";

interface RoadmapItem {
  id: string;
  title: string;
  title_ru: string;
  body: string;
  body_ru: string;
  status: Status;
  eta: string;
  eta_ru: string;
  position: number;
  is_published: boolean;
}

type Draft = Omit<RoadmapItem, "id">;

const STATUS: Record<Status, { label: string; dot: string; text: string }> = {
  exploring: { label: msg("Exploring"), dot: "bg-ink-400", text: "text-ink-400" },
  building: { label: msg("Building"), dot: "bg-signal-amber", text: "text-signal-amber" },
  beta: { label: msg("In beta"), dot: "bg-signal-sage", text: "text-signal-sage" },
};

const KEY = ["roadmap"];
const FIELD = "w-full bg-transparent border border-[var(--line-strong)] px-2.5 py-1.5 text-sm text-ink-50 outline-none focus:border-signal-amber";
const SMALL_BTN = "font-mono text-[10px] uppercase tracking-[0.14em] px-2.5 py-1.5 border transition-colors disabled:opacity-40";

function localized(item: RoadmapItem, field: "title" | "body" | "eta"): string {
  const ru = item[`${field}_ru` as const];
  return currentLang() === "ru" && ru ? ru : item[field];
}

function emptyDraft(position: number): Draft {
  return { title: "", title_ru: "", body: "", body_ru: "", status: "exploring", eta: "", eta_ru: "", position, is_published: true };
}

function Editor({ initial, onSave, onCancel, onDelete, busy }: {
  initial: Draft;
  onSave: (d: Draft) => void;
  onCancel: () => void;
  onDelete?: () => void;
  busy: boolean;
}) {
  const [d, setD] = useState<Draft>(initial);
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setD((p) => ({ ...p, [k]: v }));
  return (
    <form
      className="space-y-2.5"
      onSubmit={(e) => {
        e.preventDefault();
        if (d.title.trim()) onSave({ ...d, title: d.title.trim(), body: d.body.trim(), eta: d.eta.trim(), title_ru: d.title_ru.trim(), body_ru: d.body_ru.trim(), eta_ru: d.eta_ru.trim() });
      }}
    >
      <input className={FIELD} value={d.title} maxLength={120} placeholder={t("Title")} onChange={(e) => set("title", e.target.value)} autoFocus />
      <textarea className={`${FIELD} min-h-[88px] resize-y`} value={d.body} maxLength={600} placeholder={t("What it does, in one or two sentences")} onChange={(e) => set("body", e.target.value)} />
      <div className="grid grid-cols-[1fr_4.5rem] gap-2">
        <select className={FIELD} value={d.status} onChange={(e) => set("status", e.target.value as Status)}>
          {(Object.keys(STATUS) as Status[]).map((s) => (
            <option key={s} value={s} className="bg-ink-900">{t(STATUS[s].label)}</option>
          ))}
        </select>
        <input className={FIELD} type="number" min={0} value={d.position} title={t("Order")} aria-label={t("Order")} onChange={(e) => set("position", Math.max(0, Number(e.target.value) || 0))} />
      </div>
      <input className={FIELD} value={d.eta} maxLength={40} placeholder={t("ETA, e.g. Q1 2027 (optional)")} onChange={(e) => set("eta", e.target.value)} />
      <div className="pt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">RU</div>
      <input className={FIELD} value={d.title_ru} maxLength={120} placeholder={t("Title in Russian")} onChange={(e) => set("title_ru", e.target.value)} />
      <textarea className={`${FIELD} min-h-[88px] resize-y`} value={d.body_ru} maxLength={600} placeholder={t("Description in Russian")} onChange={(e) => set("body_ru", e.target.value)} />
      <input className={FIELD} value={d.eta_ru} maxLength={40} placeholder={t("ETA in Russian (optional)")} onChange={(e) => set("eta_ru", e.target.value)} />
      <label className="flex items-center gap-2 text-xs text-ink-400">
        <input type="checkbox" checked={d.is_published} onChange={(e) => set("is_published", e.target.checked)} className="accent-amber-400" />
        {t("Visible to visitors")}
      </label>
      <div className="flex flex-wrap gap-2 pt-1">
        <button type="submit" disabled={busy || !d.title.trim()} className={`${SMALL_BTN} border-signal-amber text-signal-amber hover:bg-white/5`}>{t("Save")}</button>
        <button type="button" onClick={onCancel} className={`${SMALL_BTN} border-[var(--line-strong)] text-ink-400 hover:text-ink-100`}>{t("Cancel")}</button>
        {onDelete && (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              if (window.confirm(t("Delete this roadmap item?"))) onDelete();
            }}
            className={`${SMALL_BTN} ml-auto border-signal-blood text-signal-blood hover:bg-white/5`}
          >
            {t("Delete")}
          </button>
        )}
      </div>
    </form>
  );
}

export default function Roadmap() {
  const isStaff = useAuthStore((s) => !!s.user?.is_staff);
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const { data: items = [], isSuccess } = useQuery<RoadmapItem[]>({
    queryKey: [...KEY, isStaff],
    queryFn: () => client.get("/system/roadmap/").then((r) => r.data),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const done = () => {
    setEditing(null);
    queryClient.invalidateQueries({ queryKey: KEY });
  };
  const fail = () => toast.error(t("Could not save the roadmap"));
  const create = useMutation({ mutationFn: (d: Draft) => client.post("/system/roadmap/", d), onSuccess: done, onError: fail });
  const update = useMutation({ mutationFn: ({ id, d }: { id: string; d: Draft }) => client.patch(`/system/roadmap/${id}/`, d), onSuccess: done, onError: fail });
  const remove = useMutation({ mutationFn: (id: string) => client.delete(`/system/roadmap/${id}/`), onSuccess: done, onError: fail });
  const busy = create.isPending || update.isPending || remove.isPending;

  if (!isSuccess || (!items.length && !isStaff)) return null;
  const nextPosition = items.reduce((m, i) => Math.max(m, i.position), 0) + 10;

  return (
    <section className="pb-28" id="roadmap">
      <motion.div
        className="flex items-end justify-between flex-wrap gap-6 mb-10"
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
      >
        <div>
          <div className="label-mono mb-3 flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-signal-amber rounded-full pulse-dot" />
            {t("On the bench next")}
          </div>
          <h2 className="font-display text-6xl lg:text-7xl text-ink-50 leading-[0.95]">
            {t("Coming")} <span className="italic text-iris">{t("soon")}</span>.
          </h2>
        </div>
        <p className="max-w-md text-ink-300 leading-relaxed">
          {t("What we are building now. Nothing here gets a vote in the Tribunal until it is measured on held-out data.")}
        </p>
      </motion.div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-px bg-[var(--line-strong)] border border-[var(--line-strong)]">
        {items.map((item, i) => {
          const s = STATUS[item.status] ?? STATUS.exploring;
          return (
            <motion.article
              key={item.id}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.06 }}
              className={`bg-ink-950 p-6 flex flex-col ${item.is_published ? "" : "opacity-60"}`}
            >
              {editing === item.id ? (
                <Editor
                  initial={item}
                  busy={busy}
                  onCancel={() => setEditing(null)}
                  onSave={(d) => update.mutate({ id: item.id, d })}
                  onDelete={() => remove.mutate(item.id)}
                />
              ) : (
                <>
                  <div className="flex items-center justify-between gap-3 font-mono text-[10px] uppercase tracking-[0.16em]">
                    <span className={`flex items-center gap-2 ${s.text}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${s.dot} ${item.status === "building" ? "pulse-dot" : ""}`} />
                      {t(s.label)}
                    </span>
                    {localized(item, "eta") && <span className="text-ink-500">{localized(item, "eta")}</span>}
                  </div>
                  <h3 className="font-display text-2xl text-ink-50 leading-tight mt-5">{localized(item, "title")}</h3>
                  {localized(item, "body") && <p className="text-sm text-ink-400 leading-relaxed mt-3">{localized(item, "body")}</p>}
                  {isStaff && (
                    <div className="mt-auto pt-5 flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.14em]">
                      <span className="text-ink-600">{item.is_published ? `#${item.position}` : "hidden"}</span>
                      <button type="button" onClick={() => setEditing(item.id)} className="text-ink-400 hover:text-signal-amber transition-colors">
                        {t("Edit")}
                      </button>
                    </div>
                  )}
                </>
              )}
            </motion.article>
          );
        })}
        {isStaff && editing === "new" && (
          <div className="bg-ink-950 p-6">
            <Editor initial={emptyDraft(nextPosition)} busy={busy} onCancel={() => setEditing(null)} onSave={(d) => create.mutate(d)} />
          </div>
        )}
      </div>
      {isStaff && editing !== "new" && (
        <button
          type="button"
          onClick={() => setEditing("new")}
          className="mt-4 w-full py-4 border border-dashed border-[var(--line-strong)] font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500 hover:text-signal-amber hover:border-signal-amber transition-colors"
        >
          + {t("Add roadmap item")}
        </button>
      )}
    </section>
  );
}
