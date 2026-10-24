import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Download, FileCheck, RefreshCw, UserMinus, Archive } from "lucide-react";
import { classrooms, objections } from "../api/endpoints";
import type { ClassRadar, JumpReason, RadarPair, RadarRef, ShadowSet, VerdictObjection } from "../types";
import { toast } from "../components/ui/Toast";
import { levelLabel, levelOptions } from "../classroom/shared";
import SubmissionRows from "../classroom/SubmissionRows";
import { currentLang, locale, msg, t, tn } from "../i18n";
import { levelName } from "../components/TeacherSummary";

const DECISION_TEXT: Record<string, string> = { upheld: msg("verdict upheld"), changed: msg("suspicion cleared") };

const BTN = "flex items-center gap-1.5 border border-[var(--line-strong)] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-300 hover:text-signal-amber";

const SHADOW_STATUS: Record<string, string> = {
  pending: msg("queued"),
  running: msg("writing answers"),
  failed: msg("failed"),
};

function shortDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString(locale()) : "";
}

function personName(ref: Pick<RadarRef, "student" | "unattributed">): string {
  return ref.unattributed ? t("No student (teacher check)") : ref.student;
}

function quote(text: string): string {
  return t("“{text}”", { text });
}

function jumpReason(reason: JumpReason, level: number | null): { label: string; text: string; extra?: string } {
  if (reason.kind === "vocabulary") {
    const words = reason.words.join(", ");
    const text = level
      ? t("much harder than usual for {level} and than this author's earlier work", { level: levelName(level) })
      : t("much harder than this author's earlier work");
    const extra = reason.words_per_sentence
      ? t("on average {now} words per sentence, earlier {before}", { now: reason.words_per_sentence.now, before: reason.words_per_sentence.before })
      : undefined;
    return { label: t("Vocabulary"), text: words ? `${text}: ${words}` : text, extra };
  }
  if (reason.kind === "ai") return { label: t("Chatbot text"), text: t("the chatbot-text check fires, earlier work by this author was ordinary") };
  return { label: t("Style"), text: t("differs sharply from earlier work by the same author") };
}

function confirmed(question: string): boolean {
  return window.confirm(question);
}

function ShadowSetRow({ s, classId, open, onToggle }: { s: ShadowSet; classId: string; open: boolean; onToggle: () => void }) {
  const queryClient = useQueryClient();
  const { data: detail } = useQuery({
    queryKey: ["classroom-shadow", classId, s.id],
    queryFn: () => classrooms.shadowDetail(classId, s.id).then((r) => r.data),
    enabled: open,
  });
  const remove = useMutation({
    mutationFn: () => classrooms.deleteShadow(classId, s.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["classroom-shadows", classId] }),
  });
  const status = s.status === "done"
    ? tn(s.answers, "ready: {n} answer of {target}", "ready: {n} answers of {target}", { target: s.target })
    : t(SHADOW_STATUS[s.status]);
  const compared = s.compared ?? 0;
  const matched = s.matched ?? [];
  return (
    <div className="py-2">
      <div className="flex items-center gap-3">
        <button type="button" onClick={onToggle} className="flex-1 text-left text-sm text-ink-100 truncate hover:text-ink-50">{s.prompt}</button>
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">{status}</span>
        <button type="button"
          onClick={() => { if (confirmed(t("Remove these AI answers? Marks on work that was already checked stay."))) remove.mutate(); }}
          className="font-mono text-[10px] uppercase text-ink-600 hover:text-signal-blood">{t("Remove")}</button>
      </div>
      {s.status === "failed" && <div className="text-xs text-signal-blood mt-1">{t("Could not write the answers. Try again later or shorten the assignment.")}</div>}
      {s.status === "done" && (
        <div className="text-xs text-ink-400 mt-1 space-y-0.5">
          <div>
            {compared > 0
              ? tn(compared, "Compared with {n} work handed in after {date}", "Compared with {n} works handed in after {date}", { date: shortDate(s.created_at) })
              : t("No work has been handed in since the answers were ready.")}
          </div>
          {matched.length > 0 ? (
            <div>
              <span className="text-signal-amber">{t("Follow these answers:")} </span>
              {matched.map((m, i) => (
                <span key={m.submission_id}>
                  {i > 0 && ", "}
                  <Link to={`/results/${m.submission_id}`} state={{ supervising: true }} className="text-ink-100 hover:text-signal-amber hover:underline">{m.student}</Link>
                  <span className="text-ink-500"> ({m.filename})</span>
                </span>
              ))}
            </div>
          ) : compared > 0 && <div className="text-signal-sage">{t("None of them follows these answers.")}</div>}
        </div>
      )}
      {open && detail && (
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
  );
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
  const create = useMutation({
    mutationFn: () => classrooms.createShadow(classId, prompt.trim(), 8),
    onSuccess: () => {
      setPrompt("");
      queryClient.invalidateQueries({ queryKey: ["classroom-shadows", classId] });
      toast.success(t("Writing AI answers to the assignment"));
    },
    onError: (e: { response?: { data?: { detail?: string; prompt?: string[] } } }) =>
      toast.error(t(e.response?.data?.detail ?? e.response?.data?.prompt?.[0] ?? "Could not start")),
  });
  return (
    <section className="mb-8 border border-[var(--line-strong)] p-4">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-1">{t("AI answers to the task")}</div>
      <p className="text-xs text-ink-500 mb-3 max-w-2xl">
        {t("Paste the assignment. An AI model writes {n} answers to it, the way students of different ages would. Every work handed in after the answers are ready is compared with them sentence by sentence. If a work closely follows one of them in the same order, it gets the mark “follows an AI answer”. Work handed in earlier is not compared.", { n: 8 })}
      </p>
      <div className="flex flex-col md:flex-row gap-2">
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={2} maxLength={2000}
          placeholder={t("Write an argumentative essay: do we still need to read books in the age of the internet?")}
          className="flex-1 bg-transparent border border-[var(--line-strong)] px-2.5 py-1.5 text-sm text-ink-50 outline-none focus:border-signal-amber" />
        <button type="button" disabled={prompt.trim().length < 15 || create.isPending} onClick={() => create.mutate()} className={`${BTN} disabled:opacity-40 self-start`}>
          {t("Generate answers")}
        </button>
      </div>
      {sets.length > 0 && (
        <div className="mt-3 divide-y divide-[var(--line)]">
          {sets.map((s) => (
            <ShadowSetRow key={s.id} s={s} classId={classId} open={open === s.id} onToggle={() => setOpen(open === s.id ? null : s.id)} />
          ))}
        </div>
      )}
    </section>
  );
}

function PairEvidence({ p }: { p: RadarPair }) {
  return (
    <div className="space-y-1">
      <div>
        {t("{a} and {b}: {k} of {n} sentences almost match, {order}.", {
          a: personName(p.a),
          b: personName(p.b),
          k: p.a_matched,
          n: p.a_sentences,
          order: p.in_order >= 0.9 ? t("in the same order") : t("mostly in the same order"),
        })}
      </div>
      {p.examples.length > 0 && (
        <div className="pl-3 border-l border-[var(--line)] space-y-1.5">
          <div className="text-ink-500">{t("For example, these sentences are almost the same:")}</div>
          {p.examples.map((e, i) => (
            <div key={i} className="grid md:grid-cols-2 gap-1 md:gap-3">
              <div><span className="text-ink-500">{personName(p.a)}: </span><span className="text-ink-200">{quote(e.a)}</span></div>
              <div><span className="text-ink-500">{personName(p.b)}: </span><span className="text-ink-200">{quote(e.b)}</span></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SimilarWorks({ radar }: { radar: ClassRadar }) {
  const refs = new Map<string, RadarRef>();
  radar.shared_skeletons.forEach((p) => {
    refs.set(p.a.submission_id, p.a);
    refs.set(p.b.submission_id, p.b);
  });
  return (
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
              {tn(group.length, "Group {i} · {n} work repeats another sentence by sentence", "Group {i} · {n} works repeat each other sentence by sentence", { i: i + 1 })}
            </div>
            <ul className="px-3 py-2 space-y-1">
              {group.map((sid) => {
                const ref = refs.get(sid);
                return (
                  <li key={sid} className="text-sm">
                    <Link to={`/results/${sid}`} state={{ supervising: true }} className="text-ink-50 hover:text-signal-amber hover:underline">{ref ? personName(ref) : sid.slice(0, 8)}</Link>
                    {ref?.filename && <span className="text-ink-400"> · {ref.filename}</span>}
                    {ref?.created_at && <span className="font-mono text-[10px] text-ink-600 ml-2">{shortDate(ref.created_at)}</span>}
                  </li>
                );
              })}
            </ul>
            <div className="px-3 py-2 border-t border-[var(--line)] text-xs text-ink-400 space-y-2">
              <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-600">{t("What matched")}</div>
              {pairs.map((p) => <PairEvidence key={p.a.submission_id + p.b.submission_id} p={p} />)}
            </div>
          </div>
        );
      })}
      {radar.clusters.length > 0 && <p className="text-[11px] text-ink-600">{t("This is not a share of copying: it shows how many sentences of one work almost repeat sentences of the other.")}</p>}
    </div>
  );
}

function LevelJumps({ radar }: { radar: ClassRadar }) {
  return (
    <div className="p-4">
      <h3 className="text-base text-ink-50">{t("Sudden change in a student's work")}</h3>
      <p className="text-xs text-ink-400 mt-1 mb-3">{t("A work lands here when a check sees something new for this student: vocabulary well above the class year and above their own earlier work, chatbot text after at least {n} ordinary earlier works, or a style unlike their own. A strong student is compared with their own level, not with the class.", { n: radar.jump_history_needed })}</p>
      {radar.level_jumps.length === 0 && <p className="text-sm text-signal-sage">{t("No sudden changes.")}</p>}
      {radar.level_jumps.slice(0, 8).map((j) => (
        <Link key={j.submission_id} to={`/results/${j.submission_id}`} state={{ supervising: true }} className="block border-l-2 border-signal-amber pl-3 py-2 mb-3 hover:bg-ink-800/40">
          <div className="text-sm">
            <span className="text-ink-50">{j.student}</span>
            <span className="text-ink-400"> · {j.filename}</span>
            <span className="font-mono text-[10px] text-ink-600 ml-2">{shortDate(j.created_at)}</span>
          </div>
          <ul className="mt-1 space-y-0.5">
            {j.reasons.map((r, k) => {
              const line = jumpReason(r, radar.level);
              return (
                <li key={k} className="text-xs">
                  <span className="text-ink-500">{line.label}: </span>
                  <span className="text-signal-amber">{line.text}</span>
                  {line.extra && <span className="block text-ink-400">{line.extra}</span>}
                </li>
              );
            })}
          </ul>
        </Link>
      ))}
      {radar.level_jumps.length > 0 && <p className="text-[11px] text-ink-600">{t("Open the work and ask the student to explain a passage in their own words.")}</p>}
    </div>
  );
}

function RadarPanel({ classId }: { classId: string }) {
  const { data: radar } = useQuery({ queryKey: ["classroom-radar", classId], queryFn: () => classrooms.radar(classId).then((r) => r.data) });
  if (!radar) return null;
  return (
    <section className="mb-8 border border-[var(--line-strong)]">
      <div className="px-4 py-3 border-b border-[var(--line-strong)]">
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{tn(radar.days, "Class radar · last {n} day", "Class radar · last {n} days")}</div>
          <div className="font-mono text-[10px] text-ink-600">{t("Handed in: {total}. Compared sentence by sentence: {compared}", { total: radar.submissions, compared: radar.compared })}</div>
        </div>
        <p className="text-sm text-ink-300 mt-1 max-w-3xl">{t("Two automatic observations across all work in this class. They are reasons to talk to a student, never proof.")}</p>
      </div>
      <div className="grid md:grid-cols-2 md:divide-x divide-y md:divide-y-0 divide-[var(--line-strong)]">
        <SimilarWorks radar={radar} />
        <LevelJumps radar={radar} />
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
      <p className="text-xs text-ink-400 mb-2 max-w-3xl">{t("A student can object to a verdict from the work page. Answer within {n} business days: keep the verdict, or clear the work if the student convinced you. A cleared work no longer counts as flagged. The student gets an email with your answer.", { n: 3 })}</p>
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
                  ? <span className="text-signal-amber">{t("waiting for your answer by {date}", { date: shortDate(o.due_at) })}</span>
                  : <span className={o.decision === "changed" ? "text-signal-sage" : "text-ink-500"}>{t(DECISION_TEXT[o.decision] ?? "answered")}{o.responded_at ? ` · ${shortDate(o.responded_at)}` : ""}</span>}
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

function BatchList({ classId }: { classId: string }) {
  const { data: list = [] } = useQuery({ queryKey: ["classroom-batches", classId], queryFn: () => classrooms.batches(classId).then((r) => r.data) });
  if (list.length === 0) return null;
  return (
    <section className="mb-8">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-1">{t("Batches of work")}</div>
      <p className="text-xs text-ink-400 mb-2">{t("Work uploaded several files at a time.")}</p>
      <div className="divide-y divide-[var(--line-strong)]">
        {list.map((b) => (
          <Link key={b.id} to={`/batches/${b.id}`} className="flex items-center gap-3 py-2 hover:bg-ink-800/40 px-2 -mx-2 transition-colors">
            <span className="flex-1 text-ink-100 truncate">{b.name || t("Untitled batch")}</span>
            <span className="font-mono text-[11px] text-ink-500">{shortDate(b.created_at)}</span>
            <span className="font-mono text-[11px] text-ink-500">{tn(b.total, "{n} work", "{n} works")}</span>
            <span className={`font-mono text-[11px] ${b.flagged ? "text-signal-blood" : "text-ink-600"}`}>{t("{n} flagged", { n: b.flagged })}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function fileName(name: string): string {
  return `${name.replace(/[\\/:*?"<>|]+/g, " ").trim() || "class"}.csv`;
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
    mutationFn: ({ level }: { level: number | null; previous: number | null }) => classrooms.update(id, { level }),
    onSuccess: (_, { level, previous }) => {
      queryClient.invalidateQueries({ queryKey: ["classroom", id] });
      const handedIn = !!stats && stats.total > 0;
      if (level == null) toast.success(t("Year of study removed. New work is not compared with the students' age."));
      else if (handedIn && previous != null) toast.success(t("Saved: {level}. Work handed in earlier was checked for {old}.", { level: levelLabel(level), old: levelLabel(previous) }));
      else if (handedIn) toast.success(t("Saved: {level}. Work handed in earlier was checked without it.", { level: levelLabel(level) }));
      else toast.success(t("Saved: {level}.", { level: levelLabel(level) }));
    },
  });

  const exportCsv = async () => {
    try {
      const res = await classrooms.exportCsv(id, currentLang());
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName(cls?.name ?? id);
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error(t("Export failed"));
    }
  };

  if (!cls) return <p className="text-ink-500">{t("Loading…")}</p>;

  const filterButtons: [string, string][] = [["flagged", t("Only flagged")], ["", t("All works")]];
  const studentName = roster.find((m) => m.user_id === filter.student)?.name;

  const emptyList = filter.student != null
    ? t("This student has not handed in any work yet.")
    : filter.verdict === "flagged" && stats && stats.total > 0
      ? (
        <span className="flex items-center gap-3 flex-wrap">
          <span>{t("No flagged works. Handed in: {n}.", { n: stats.total })}</span>
          <button type="button" onClick={() => setFilter({})} className="px-2 py-1 border border-[var(--line-strong)] font-mono text-[10px] uppercase tracking-[0.14em] text-ink-300 hover:text-signal-amber">{t("Show all works")}</button>
        </span>
      )
      : t("Nothing handed in yet. Share the join code with your students.");

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
            <button type="button" aria-label={t("Copy code")} title={t("Copy code")} onClick={() => navigator.clipboard.writeText(cls.join_code || "")} className="text-ink-400 hover:text-signal-amber"><Copy size={13} /></button>
            <button type="button" aria-label={t("New code")} title={t("New code")}
              onClick={() => { if (confirmed(t("Issue a new code? The old code {code} will stop working.", { code: cls.join_code ?? "" }))) rotate.mutate(); }}
              className="text-ink-400 hover:text-signal-amber"><RefreshCw size={13} /></button>
          </div>
          <label className="flex items-center gap-2 border border-[var(--line-strong)] px-3 py-1" title={t("Used to check whether vocabulary fits the students' age")}>
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("Year of study:")}</span>
            <select
              value={cls.level ?? ""}
              onChange={(e) => setLevel.mutate({ level: e.target.value === "" ? null : Number(e.target.value), previous: cls.level ?? null })}
              className="bg-ink-950 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-300 focus:text-signal-amber outline-none"
            >
              <option value="">{t("Year not set")}</option>
              {levelOptions().map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
          <Link to="submit" className="flex items-center gap-1.5 border border-signal-amber/60 text-signal-amber px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] hover:bg-signal-amber/10"><FileCheck size={13} /> {t("Check work")}</Link>
          <button type="button" onClick={exportCsv} className={BTN}><Download size={13} /> {t("Download table (Excel)")}</button>
          <button type="button"
            onClick={() => { if (cls.archived || confirmed(t("Move the class to the archive? Students will not be able to hand in work."))) archive.mutate(); }}
            className={BTN}><Archive size={13} /> {cls.archived ? t("Restore") : t("Archive")}</button>
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

      <ObjectionRows classId={id} />

      <p className="text-sm text-ink-400 mb-6 max-w-3xl">
        {t("Every work goes through several checks: chatbot text, disguised letters and hidden text, copying from other work and the web, vocabulary for the student's age, the student's own style, cited sources and AI answers to the assignment. Each work below lists what its checks found. A flag is a reason to talk to the student, not proof.")}
      </p>

      <RadarPanel classId={id} />
      <ShadowPanel classId={id} />
      <BatchList classId={id} />

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
                    className={`flex-1 min-w-0 text-left ${filter.student === m.user_id ? "text-signal-amber" : "text-ink-100 hover:text-ink-50"}`}>
                    <span className="block truncate">{m.name}</span>
                    {m.name !== m.username && <span className="block font-mono text-[10px] text-ink-600 truncate">{m.username}</span>}
                  </button>
                  <span className="font-mono text-[11px] text-ink-500 tabular-nums" title={t("submissions")}>{m.total}</span>
                  <span className={`font-mono text-[11px] tabular-nums ${m.flagged ? "text-signal-blood" : "text-ink-600"}`} title={t("flagged")}>{t("{n} flagged", { n: m.flagged })}</span>
                  <Link to={`submit?student=${m.user_id}`} aria-label={t("Check work by {name}", { name: m.name })} title={t("Check work by {name}", { name: m.name })} className="text-ink-600 hover:text-signal-amber"><FileCheck size={13} /></Link>
                  <button type="button" aria-label={t("Take out of class")} title={t("Take out of class")}
                    onClick={() => { if (confirmed(t("Remove {name} from the class? Their work stays in the list, but they will not be able to hand in new work.", { name: m.name }))) dropStudent.mutate(m.user_id); }}
                    className="text-ink-600 hover:text-signal-blood"><UserMinus size={13} /></button>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="lg:col-span-8">
          <div className="flex items-center gap-2 mb-2 font-mono text-[10px] uppercase tracking-[0.16em] flex-wrap">
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
              <button type="button" onClick={() => setFilter({ verdict: "flagged" })} className="px-2 py-1 border border-signal-amber/60 text-signal-amber normal-case tracking-normal">
                {t("{name} · show everyone", { name: studentName ?? "" })}
              </button>
            )}
          </div>
          <SubmissionRows rows={rows} viewer="teacher" empty={emptyList} />
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
          <span className="label-mono">{t("Teacher: {name}", { name: cls.owner_name })}</span>
          <h1 className="font-display text-4xl text-white mt-2">{cls.name}</h1>
          <p className="text-sm text-ink-400 mt-2">{t("Your teacher sees only the work you hand in to this class.")}</p>
        </div>
        <div className="flex gap-2">
          <Link to="submit" className="border border-signal-amber/60 text-signal-amber px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] hover:bg-signal-amber/10">{t("Submit work")}</Link>
          <button type="button"
            onClick={() => { if (confirmed(t("Leave the class? You can come back with the class code from your teacher."))) exit.mutate(); }}
            className="border border-[var(--line-strong)] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400 hover:text-signal-blood">{t("Leave")}</button>
        </div>
      </div>
      <SubmissionRows rows={rows} viewer="student" empty={t("You have not handed in any work to this class yet.")} />
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
