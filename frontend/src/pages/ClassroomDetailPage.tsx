import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Download, FileCheck, RefreshCw, UserMinus, Archive } from "lucide-react";
import { classrooms, objections } from "../api/endpoints";
import type { ClassSubmission, RadarRef, VerdictObjection } from "../types";
import { toast } from "../components/ui/Toast";
import { levelOptions } from "../classroom/shared";
import { locale, msg, t, tn } from "../i18n";
import { VERDICT_DISCLAIMER } from "../legal";
import { PLAIN_VERDICT, STATUS_TEXT } from "../components/TeacherSummary";

const FLAG_TEXT: Record<string, string> = {
  ai_text: msg("chatbot text"),
  ai_trace: msg("AI generator trace"),
  trace_hidden: msg("AI trace damaged"),
  ai_image: msg("looks AI-generated"),
  hidden_text: msg("hidden text in file"),
  tricks: msg("disguised letters"),
  shadow: msg("follows an AI answer"),
  copy: msg("copied {n}%"),
  sources: msg("invented sources"),
  age: msg("vocabulary above age"),
  style: msg("unlike own earlier work"),
};
const STRONG_FLAGS = new Set(["ai_text", "ai_trace", "trace_hidden", "ai_image", "hidden_text", "tricks", "shadow", "sources"]);
const BAND_TEXT: Record<string, string> = {
  primary: msg("primary school"),
  middle: msg("grades 5-9"),
  senior: msg("grades 10-11"),
  university: msg("university"),
};
const DECISION_TEXT: Record<string, string> = { upheld: msg("verdict upheld"), changed: msg("verdict changed") };

function flagChip(flag: string, originality: number | null) {
  const text = flag === "copy" ? t(FLAG_TEXT.copy, { n: 100 - Math.round(originality ?? 100) }) : t(FLAG_TEXT[flag] ?? flag);
  const tone = STRONG_FLAGS.has(flag) ? "border-signal-blood/50 text-signal-blood" : "border-signal-amber/50 text-signal-amber";
  return <span key={flag} className={`inline-block border px-1.5 py-0.5 text-[10px] leading-tight ${tone}`}>{text}</span>;
}

const BTN = "flex items-center gap-1.5 border border-[var(--line-strong)] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-300 hover:text-signal-amber";

function SubmissionRows({ rows, showStudent }: { rows: ClassSubmission[]; showStudent: boolean }) {
  if (rows.length === 0) return <p className="text-sm text-ink-500 py-4">{t("Nothing submitted yet.")}</p>;
  return (
    <div className="divide-y divide-[var(--line-strong)]">
      <div className="hidden md:grid md:grid-cols-12 gap-3 pb-1 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-600">
        {showStudent && <span className="md:col-span-2">{t("Student")}</span>}
        <span className={showStudent ? "md:col-span-5" : "md:col-span-7"}>{t("Work and what the checks found")}</span>
        <span className="md:col-span-2">{t("Size")}</span>
        <span className="md:col-span-3">{t("Result")}</span>
      </div>
      {rows.map((s) => (
        <Link key={s.id} to={`/results/${s.id}`} state={{ supervising: showStudent }}
          className="grid grid-cols-[1fr_auto] md:grid-cols-12 gap-3 items-center py-3 hover:bg-ink-800/40 px-2 -mx-2 transition-colors">
          {showStudent && (
            <span className="md:col-span-2 text-ink-300 truncate">
              {s.student}
              {s.uploaded_by && <span className="block font-mono text-[10px] text-ink-600 truncate">{t("uploaded by {name}", { name: s.uploaded_by })}</span>}
            </span>
          )}
          <span className={`${showStudent ? "md:col-span-5" : "md:col-span-7"} min-w-0`}>
            <span className="block text-ink-50 truncate">{s.original_filename}</span>
            {s.status === "completed" && (
              <span className="flex flex-wrap gap-1 mt-1">
                {s.flags.length > 0
                  ? s.flags.map((f) => flagChip(f, s.originality))
                  : <span className="text-[10px] text-signal-sage">{t("no check raised a concern")}</span>}
              </span>
            )}
          </span>
          <span className="md:col-span-2 font-mono text-[11px] text-ink-500 hidden md:block">
            {s.words != null ? tn(s.words, "{n} word", "{n} words") : t(s.mime_type.split("/")[0])}
            {s.originality != null && <span className={s.originality < 60 ? "text-signal-blood" : s.originality < 85 ? "text-signal-amber" : "text-signal-sage"}> · {t("{n}% original", { n: Math.round(s.originality) })}</span>}
          </span>
          <span className="md:col-span-3 flex flex-col">
            <span className={`text-sm leading-snug ${PLAIN_VERDICT[s.final_verdict] ? STATUS_TEXT[PLAIN_VERDICT[s.final_verdict].status] : "text-ink-400"}`}>
              {s.status === "completed" ? (PLAIN_VERDICT[s.final_verdict] ? t(PLAIN_VERDICT[s.final_verdict].teacher) : "-") : t(s.status)}
            </span>
            {s.status === "completed" && s.final_verdict && (
              <span className="text-[10px] leading-snug text-ink-600 mt-0.5">
                {s.final_score != null && <span className="font-mono text-ink-500">{t("risk {n}%", { n: Math.round(s.final_score * 100) })} · </span>}
                {t(VERDICT_DISCLAIMER)}
              </span>
            )}
          </span>
        </Link>
      ))}
    </div>
  );
}

const SHADOW_STATUS: Record<string, string> = {
  pending: msg("queued"),
  running: msg("writing answers"),
  done: msg("ready"),
  failed: msg("failed"),
};

type JumpReason = { kind: "readability"; now: string; before: string } | { kind: "ai" } | { kind: "style" };

function jumpReason(reason: JumpReason): { label: string; text: string } {
  if (reason.kind === "readability") {
    const text = reason.now === reason.before
      ? t("sentences and words are much longer than in this student's earlier work")
      : t("reads like {now} writing, earlier work read like {before}", { now: t(BAND_TEXT[reason.now]), before: t(BAND_TEXT[reason.before]) });
    return { label: t("Text complexity"), text };
  }
  if (reason.kind === "ai") return { label: t("Chatbot text"), text: t("the classifier sees machine writing, this student's earlier work was ordinary") };
  return { label: t("Style"), text: t("differs sharply from this student's earlier work") };
}

function ShadowPanel({ classId }: { classId: string }) {
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const { data: sets = [] } = useQuery({
    queryKey: ["classroom-shadows", classId],
    queryFn: () => classrooms.shadows(classId).then((r) => r.data),
    refetchInterval: (query) => (query.state.data ?? []).some((s) => s.status === "pending" || s.status === "running") ? 10000 : false,
  });
  const { data: detail } = useQuery({
    queryKey: ["classroom-shadow", classId, open],
    queryFn: () => classrooms.shadowDetail(classId, open!).then((r) => r.data),
    enabled: !!open,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["classroom-shadows", classId] });
  const create = useMutation({
    mutationFn: () => classrooms.createShadow(classId, prompt.trim(), 8),
    onSuccess: () => { setPrompt(""); refresh(); toast.success(t("Writing AI answers to the assignment")); },
    onError: (e: { response?: { data?: { detail?: string; prompt?: string[] } } }) =>
      toast.error(t(e.response?.data?.detail ?? e.response?.data?.prompt?.[0] ?? "Could not start")),
  });
  const remove = useMutation({ mutationFn: (sid: string) => classrooms.deleteShadow(classId, sid), onSuccess: refresh });
  return (
    <section className="mb-8 border border-[var(--line-strong)] p-4">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-1">{t("Assignment shadow")}</div>
      <p className="text-xs text-ink-500 mb-3 max-w-2xl">
        {t("Paste the assignment. We ask an AI model to answer it as students of different ages would, then compare every work in this class with those answers sentence by sentence. A close match in the same order sends the work to review.")}
      </p>
      <div className="flex flex-col md:flex-row gap-2">
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={2} maxLength={2000}
          placeholder="Напишите сочинение-рассуждение: нужно ли читать книги в эпоху интернета?"
          className="flex-1 bg-transparent border border-[var(--line-strong)] px-2.5 py-1.5 text-sm text-ink-50 outline-none focus:border-signal-amber" />
        <button type="button" disabled={prompt.trim().length < 15 || create.isPending} onClick={() => create.mutate()} className={`${BTN} disabled:opacity-40 self-start`}>
          {t("Generate answers")}
        </button>
      </div>
      {sets.length > 0 && (
        <div className="mt-3 divide-y divide-[var(--line)]">
          {sets.map((s) => (
            <div key={s.id} className="py-2">
              <div className="flex items-center gap-3">
                <button type="button" onClick={() => setOpen(open === s.id ? null : s.id)} className="flex-1 text-left text-sm text-ink-100 truncate hover:text-ink-50">{s.prompt}</button>
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">{t(SHADOW_STATUS[s.status])} · {s.answers}/{s.target}</span>
                <button type="button" onClick={() => remove.mutate(s.id)} className="font-mono text-[10px] uppercase text-ink-600 hover:text-signal-blood">{t("Remove")}</button>
              </div>
              {s.error && <div className="text-xs text-signal-blood mt-1">{s.error}</div>}
              {open === s.id && detail && (
                <div className="mt-2 space-y-2">
                  {detail.texts.slice(0, 3).map((a) => (
                    <div key={a.variant + a.text.slice(0, 20)} className="text-xs text-ink-400 border-l border-[var(--line-strong)] pl-3">
                      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-600 mb-1">{a.variant}</div>
                      {a.text.slice(0, 600)}{a.text.length > 600 ? "..." : ""}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function RadarPanel({ classId }: { classId: string }) {
  const { data: radar } = useQuery({ queryKey: ["classroom-radar", classId], queryFn: () => classrooms.radar(classId).then((r) => r.data) });
  if (!radar) return null;
  const refs = new Map<string, RadarRef>();
  radar.shared_skeletons.forEach((p) => {
    refs.set(p.a.submission_id, p.a);
    refs.set(p.b.submission_id, p.b);
  });
  const date = (iso: string) => new Date(iso).toLocaleDateString(locale());
  return (
    <section className="mb-8 border border-[var(--line-strong)]">
      <div className="px-4 py-3 border-b border-[var(--line-strong)]">
        <div className="flex items-baseline justify-between gap-3">
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{tn(radar.days, "Class radar · last {n} day", "Class radar · last {n} days")}</div>
          <div className="font-mono text-[10px] text-ink-600">{tn(radar.submissions, "{n} work compared", "{n} works compared")}</div>
        </div>
        <p className="text-sm text-ink-300 mt-1 max-w-3xl">{t("Two automatic observations across all work in this class. They are reasons to talk to a student, never proof.")}</p>
      </div>
      <div className="grid md:grid-cols-2 md:divide-x divide-y md:divide-y-0 divide-[var(--line-strong)]">
        <div className="p-4">
          <h3 className="text-base text-ink-50">{t("Similar works")}</h3>
          <p className="text-xs text-ink-400 mt-1 mb-3">{t("Every work is compared with every other one sentence by sentence. When almost every sentence of one work has a near copy in another, in the same order, the two most likely share a source: one chatbot request, one article or one outline.")}</p>
          {!radar.skeleton_data.enough && (
            <p className="text-sm text-ink-400">
              {t("Nothing to compare yet: at least {needWorks} works from {needStudents} students are needed. Now: {works} works from {students} students.", { works: radar.skeleton_data.works, needWorks: radar.skeleton_data.need_works, students: radar.skeleton_data.students, needStudents: radar.skeleton_data.need_students })}
            </p>
          )}
          {radar.skeleton_data.enough && radar.clusters.length === 0 && <p className="text-sm text-signal-sage">{t("No similar works.")}</p>}
          {radar.clusters.map((group, i) => {
            const pairs = radar.shared_skeletons.filter((p) => group.includes(p.a.submission_id) && group.includes(p.b.submission_id));
            return (
              <div key={group.join()} className="border border-signal-amber/40 mb-3">
                <div className="px-3 py-2 bg-signal-amber/5 text-xs text-signal-amber">
                  {t("Group {i} · {n} works, most likely one source", { i: i + 1, n: group.length })}
                </div>
                <ul className="px-3 py-2 space-y-1">
                  {group.map((sid) => {
                    const ref = refs.get(sid);
                    return (
                      <li key={sid} className="text-sm">
                        <Link to={`/results/${sid}`} state={{ supervising: true }} className="text-ink-50 hover:text-signal-amber hover:underline">{ref?.student ?? sid.slice(0, 8)}</Link>
                        {ref?.filename && <span className="text-ink-400"> · {ref.filename}</span>}
                        {ref?.created_at && <span className="font-mono text-[10px] text-ink-600 ml-2">{date(ref.created_at)}</span>}
                      </li>
                    );
                  })}
                </ul>
                <div className="px-3 py-2 border-t border-[var(--line)] text-xs text-ink-400 space-y-0.5">
                  <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-600">{t("What matched")}</div>
                  {pairs.map((p) => (
                    <div key={p.a.submission_id + p.b.submission_id}>
                      {t("{a} and {b}: {share}% of sentences match, {order}", {
                        a: p.a.student,
                        b: p.b.student,
                        share: Math.round(100 * p.aligned_share),
                        order: p.in_order >= 0.9 ? t("same order") : t("mostly the same order"),
                      })}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
          {radar.clusters.length > 0 && <p className="text-[11px] text-ink-600">{t("100% means every sentence of one work has a near copy in the other.")}</p>}
        </div>
        <div className="p-4">
          <h3 className="text-base text-ink-50">{t("Sudden jump in level")}</h3>
          <p className="text-xs text-ink-400 mt-1 mb-3">{t("Each new work is compared with the same student's earlier work (at least {n} pieces). A work lands here when it is suddenly written far above how this student wrote before, or when the classifier sees chatbot text where earlier work was ordinary. A strong student is compared with their own level, not with the class.", { n: radar.jump_history_needed })}</p>
          {radar.level_jumps.length === 0 && <p className="text-sm text-signal-sage">{t("No jumps.")}</p>}
          {radar.level_jumps.slice(0, 8).map((j) => (
            <Link key={j.submission_id} to={`/results/${j.submission_id}`} state={{ supervising: true }} className="block border-l-2 border-signal-amber pl-3 py-2 mb-3 hover:bg-ink-800/40">
              <div className="text-sm">
                <span className="text-ink-50">{j.student}</span>
                <span className="text-ink-400"> · {j.filename}</span>
                <span className="font-mono text-[10px] text-ink-600 ml-2">{date(j.created_at)}</span>
              </div>
              <ul className="mt-1 space-y-0.5">
                {j.reasons.map((r, k) => {
                  const line = jumpReason(r);
                  return (
                    <li key={k} className="text-xs">
                      <span className="text-ink-500">{line.label}: </span>
                      <span className="text-signal-amber">{line.text}</span>
                    </li>
                  );
                })}
              </ul>
            </Link>
          ))}
          {radar.level_jumps.length > 0 && <p className="text-[11px] text-ink-600">{t("Open the work and ask the student to explain a passage in their own words.")}</p>}
        </div>
      </div>
    </section>
  );
}

function ObjectionRows({ classId }: { classId: string }) {
  const { data: all = [] } = useQuery({
    queryKey: ["classroom-subs", classId, "all"],
    queryFn: () => classrooms.submissions(classId).then((r) => r.data),
    refetchInterval: 60000,
  });
  const { data: listed = [] } = useQuery({
    queryKey: ["objections", "all"],
    queryFn: () => objections.list({ page_size: 200 }).then((r) => r.data.results),
    refetchInterval: 60000,
  });
  const ids = new Set(all.map((s) => s.id));
  const rows: VerdictObjection[] = listed.filter((o) => ids.has(o.submission_id));
  const open = rows.filter((o) => o.status === "open");
  const answered = rows.filter((o) => o.status !== "open");

  return (
    <section className="mb-8">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-1">
        {t("Objections")} {open.length > 0 && <span className="text-signal-amber">· {t("{n} open", { n: open.length })}</span>}
      </div>
      <p className="text-xs text-ink-400 mb-2 max-w-3xl">{t("A student can object to a verdict from the work page. The teacher answers within {n} business days: keeps the verdict or changes it.", { n: 3 })}</p>
      {rows.length === 0 ? (
        <p className="text-sm text-ink-500">{t("No objections in this class.")}</p>
      ) : (
        <div className="divide-y divide-[var(--line-strong)]">
          {[...open, ...answered].map((o) => (
            <Link key={o.id} to={`/results/${o.submission_id}`} state={{ supervising: true }}
              className="grid grid-cols-[1fr_auto] md:grid-cols-12 gap-3 items-center py-3 hover:bg-ink-800/40 px-2 -mx-2 transition-colors">
              <span className="md:col-span-2 text-ink-300 truncate">{o.student}</span>
              <span className="md:col-span-6 min-w-0">
                <span className="block text-ink-50 truncate">{o.submission_title}</span>
                <span className="block text-xs text-ink-500 truncate">{t("Student: {reason}", { reason: o.reason })}</span>
                {o.response && <span className="block text-xs text-ink-400 truncate">{t("Teacher: {response}", { response: o.response })}</span>}
              </span>
              <span className="md:col-span-4 flex items-center justify-end gap-2 font-mono text-[11px] text-ink-400">
                {o.status === "open" && o.overdue && (
                  <span className="border border-signal-blood/60 text-signal-blood px-1.5 py-0.5 text-[9px] uppercase tracking-[0.14em]">{t("Overdue")}</span>
                )}
                {o.status === "open"
                  ? <span className="text-signal-amber">{t("waiting for your answer by {date}", { date: new Date(o.due_at).toLocaleDateString(locale()) })}</span>
                  : <span className="text-ink-500">{t(DECISION_TEXT[o.decision] ?? "answered")}{o.responded_at ? ` · ${new Date(o.responded_at).toLocaleDateString(locale())}` : ""}</span>}
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

function TeacherView({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<{ student?: number; verdict?: string }>({ verdict: "flagged" });
  const { data: cls } = useQuery({ queryKey: ["classroom", id], queryFn: () => classrooms.detail(id).then((r) => r.data) });
  const { data: stats } = useQuery({ queryKey: ["classroom-stats", id], queryFn: () => classrooms.stats(id).then((r) => r.data), refetchInterval: 15000 });
  const { data: roster = [] } = useQuery({ queryKey: ["classroom-roster", id], queryFn: () => classrooms.roster(id).then((r) => r.data) });
  const { data: rows = [] } = useQuery({
    queryKey: ["classroom-subs", id, filter],
    queryFn: () => classrooms.submissions(id, filter).then((r) => r.data),
    refetchInterval: 15000,
  });

  const rotate = useMutation({
    mutationFn: () => classrooms.rotateCode(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["classroom", id] });
      toast.success(t("New join code issued; the old one no longer works"));
    },
  });
  const dropStudent = useMutation({
    mutationFn: (userId: number) => classrooms.removeMember(id, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["classroom-roster", id] }),
  });
  const archive = useMutation({
    mutationFn: () => classrooms.update(id, { archived: !cls?.archived }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["classrooms"] });
      navigate(cls?.organization_slug ? `/${cls.organization_slug}` : "/");
    },
  });

  const setLevel = useMutation({
    mutationFn: (level: number | null) => classrooms.update(id, { level }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["classroom", id] });
      toast.success(t("Class year saved; new work is checked against it"));
    },
  });

  const exportCsv = async () => {
    try {
      const res = await classrooms.exportCsv(id);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `prooflayer_class_${id}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error(t("Export failed"));
    }
  };

  if (!cls) return <p className="text-ink-500">{t("Loading…")}</p>;

  const filterButtons: [string, string][] = [["flagged", t("Only flagged")], ["", t("All works")]];

  return (
    <div>
      <div className="flex items-end justify-between flex-wrap gap-4 mb-6">
        <div>
          <span className="label-mono">{t("Classroom · teacher")}</span>
          <h1 className="font-display text-4xl text-white mt-2">{cls.name}</h1>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-2 border border-[var(--line-strong)] px-3 py-1.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("join code")}</span>
            <span className="font-mono tracking-[0.2em] text-ink-50">{cls.join_code}</span>
            <button type="button" aria-label={t("Copy code")} onClick={() => navigator.clipboard.writeText(cls.join_code || "")} className="text-ink-400 hover:text-signal-amber"><Copy size={13} /></button>
            <button type="button" aria-label={t("New code")} onClick={() => rotate.mutate()} className="text-ink-400 hover:text-signal-amber"><RefreshCw size={13} /></button>
          </div>
          <select
            value={cls.level ?? ""}
            onChange={(e) => setLevel.mutate(e.target.value === "" ? null : Number(e.target.value))}
            aria-label={t("Class year")}
            title={t("Used to check whether vocabulary fits the students' age")}
            className="bg-ink-950 border border-[var(--line-strong)] px-2 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-300 focus:border-signal-amber outline-none"
          >
            <option value="">{t("Year not set")}</option>
            {levelOptions().map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <Link to="submit" className="flex items-center gap-1.5 border border-signal-amber/60 text-signal-amber px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] hover:bg-signal-amber/10"><FileCheck size={13} /> {t("Check work")}</Link>
          <button type="button" onClick={exportCsv} className={BTN}><Download size={13} /> CSV</button>
          <button type="button" onClick={() => archive.mutate()} className={BTN}><Archive size={13} /> {cls.archived ? t("Restore") : t("Archive")}</button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-[var(--line-strong)] mb-8">
          {[
            [t("Students"), String(stats.students), t("in this class")],
            [t("Submissions"), String(stats.total), t("checked in this class")],
            [t("Flagged"), String(stats.flagged), t("works where at least one check asks for attention")],
            [t("Flagged share"), `${Math.round(stats.flagged_share * 100)}%`, t("of all checked works")],
          ].map(([label, value, note]) => (
            <div key={label} className="bg-ink-950 p-4">
              <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{label}</div>
              <div className="font-display text-3xl text-ink-50 mt-1 tabular-nums">{value}</div>
              <div className="text-[11px] text-ink-600 mt-1">{note}</div>
            </div>
          ))}
        </div>
      )}

      <p className="text-sm text-ink-400 mb-6 max-w-3xl">
        {t("Every work goes through several checks: chatbot text, disguised letters and hidden text, copying from other work and the web, vocabulary for the student's age, the student's own style, cited sources and AI answers to the assignment. Each work below lists what its checks found. A flag is a reason to talk to the student, not proof.")}
      </p>

      <RadarPanel classId={id} />
      <ShadowPanel classId={id} />

      <ObjectionRows classId={id} />

      <div className="grid lg:grid-cols-12 gap-8">
        <section className="lg:col-span-4">
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-1">{t("Students")}</div>
          <p className="text-xs text-ink-500 mb-2">{t("Click a name to see only that student's work. Numbers: works handed in and works with a flag.")}</p>
          {roster.length === 0 ? (
            <p className="text-sm text-ink-500">{t("Share the join code with your students.")}</p>
          ) : (
            <div className="divide-y divide-[var(--line-strong)]">
              {roster.map((m) => (
                <div key={m.user_id} className="flex items-center gap-3 py-2">
                  <button type="button" onClick={() => setFilter({ student: m.user_id })}
                    className={`flex-1 text-left truncate ${filter.student === m.user_id ? "text-signal-amber" : "text-ink-100 hover:text-ink-50"}`}>
                    {m.username}
                  </button>
                  <span className="font-mono text-[11px] text-ink-500 tabular-nums" title={t("submissions")}>{m.total}</span>
                  <span className={`font-mono text-[11px] tabular-nums ${m.flagged ? "text-signal-blood" : "text-ink-600"}`} title={t("flagged")}>{t("{n} flagged", { n: m.flagged })}</span>
                  <Link to={`submit?student=${m.user_id}`} aria-label={t("Check work by {name}", { name: m.username })} title={t("Check work by {name}", { name: m.username })} className="text-ink-600 hover:text-signal-amber"><FileCheck size={13} /></Link>
                  <button type="button" aria-label={t("Take out of class")} onClick={() => dropStudent.mutate(m.user_id)} className="text-ink-600 hover:text-signal-blood"><UserMinus size={13} /></button>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="lg:col-span-8">
          <div className="flex items-center gap-2 mb-2 font-mono text-[10px] uppercase tracking-[0.16em]">
            {filterButtons.map(([value, label]) => {
              const active = filter.student == null && (filter.verdict ?? "") === value;
              return (
                <button key={label} type="button" onClick={() => setFilter(value ? { verdict: value } : {})}
                  className={`px-2 py-1 border ${active ? "border-signal-amber/60 text-signal-amber" : "border-[var(--line-strong)] text-ink-400"}`}>
                  {label}
                </button>
              );
            })}
            {filter.student != null && (
              <button type="button" onClick={() => setFilter({ verdict: "flagged" })} className="px-2 py-1 border border-signal-amber/60 text-signal-amber">
                {t("one student · show all")}
              </button>
            )}
          </div>
          <SubmissionRows rows={rows} showStudent />
        </section>
      </div>
    </div>
  );
}

function StudentView({ id }: { id: string }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: cls } = useQuery({ queryKey: ["classroom", id], queryFn: () => classrooms.detail(id).then((r) => r.data) });
  const { data: rows = [] } = useQuery({
    queryKey: ["classroom-subs", id, "mine"],
    queryFn: () => classrooms.submissions(id).then((r) => r.data),
    refetchInterval: 15000,
  });
  const exit = useMutation({
    mutationFn: () => classrooms.leave(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["classrooms"] });
      navigate(cls?.organization_slug ? `/${cls.organization_slug}` : "/");
    },
  });
  if (!cls) return <p className="text-ink-500">{t("Loading…")}</p>;
  return (
    <div>
      <div className="flex items-end justify-between flex-wrap gap-4 mb-6">
        <div>
          <span className="label-mono">{t("Classroom")} · {cls.owner_name}</span>
          <h1 className="font-display text-4xl text-white mt-2">{cls.name}</h1>
          <p className="text-sm text-ink-400 mt-2">{t("Your teacher sees only what you submit to this class, never your personal checks.")}</p>
        </div>
        <div className="flex gap-2">
          <Link to="submit" className="border border-signal-amber/60 text-signal-amber px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] hover:bg-signal-amber/10">{t("Submit work")}</Link>
          <button type="button" onClick={() => exit.mutate()} className="border border-[var(--line-strong)] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400 hover:text-signal-blood">{t("Leave")}</button>
        </div>
      </div>
      <SubmissionRows rows={rows} showStudent={false} />
    </div>
  );
}

export default function ClassroomDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: cls, isError } = useQuery({ queryKey: ["classroom", id], queryFn: () => classrooms.detail(id!).then((r) => r.data), enabled: !!id });
  if (isError) return <p className="text-ink-500">{t("Classroom not found.")}</p>;
  if (!cls || !id) return <p className="text-ink-500">{t("Loading…")}</p>;
  return cls.role === "teacher" ? <TeacherView id={id} /> : <StudentView id={id} />;
}
