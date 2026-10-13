import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Download, RefreshCw, UserMinus, Archive } from "lucide-react";
import { classrooms, objections } from "../api/endpoints";
import type { ClassSubmission, VerdictObjection } from "../types";
import { toast } from "../components/ui/Toast";
import { LEVEL_OPTIONS } from "../classroom/shared";
import { VERDICT_DISCLAIMER } from "../legal";

const VERDICT_CLASS: Record<string, string> = {
  fake: "text-signal-blood", likely_fake: "text-signal-blood",
  suspicious: "text-signal-amber", needs_review: "text-signal-amber",
  authentic: "text-signal-sage", authentic_edited: "text-signal-sage",
};

const BTN = "flex items-center gap-1.5 border border-[var(--line-strong)] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-300 hover:text-signal-amber";

function SubmissionRows({ rows, showStudent }: { rows: ClassSubmission[]; showStudent: boolean }) {
  if (rows.length === 0) return <p className="text-sm text-ink-500 py-4">Nothing submitted yet.</p>;
  return (
    <div className="divide-y divide-[var(--line-strong)]">
      {rows.map((s) => (
        <Link key={s.id} to={`/results/${s.id}`} state={{ supervising: showStudent }}
          className="grid grid-cols-[1fr_auto] md:grid-cols-12 gap-3 items-center py-3 hover:bg-ink-800/40 px-2 -mx-2 transition-colors">
          {showStudent && <span className="md:col-span-2 text-ink-300 truncate">{s.student}</span>}
          <span className={`${showStudent ? "md:col-span-5" : "md:col-span-7"} text-ink-50 truncate`}>{s.original_filename}</span>
          <span className="md:col-span-2 font-mono text-[11px] text-ink-500 hidden md:block">
            {s.words != null ? `${s.words} words` : s.mime_type.split("/")[0]}
            {s.originality != null && <span className={s.originality < 60 ? "text-signal-blood" : s.originality < 85 ? "text-signal-amber" : "text-signal-sage"}> · {Math.round(s.originality)}% orig.</span>}
          </span>
          <span className="md:col-span-2 flex flex-col">
            <span className={`font-mono text-[11px] uppercase tracking-[0.12em] ${VERDICT_CLASS[s.final_verdict] || "text-ink-400"}`}>
              {s.status === "completed" ? s.final_verdict.replace("_", " ") || "-" : s.status}
            </span>
            {s.status === "completed" && s.final_verdict && (
              <span className="text-[10px] leading-snug text-ink-600 mt-0.5">{VERDICT_DISCLAIMER}</span>
            )}
          </span>
          <span className="md:col-span-1 font-mono text-[11px] text-ink-400 text-right hidden md:block">
            {s.final_score != null ? `${Math.round(s.final_score * 100)}%` : ""}
          </span>
        </Link>
      ))}
    </div>
  );
}

function ObjectionRows({ classId }: { classId: string }) {
  const { data: all = [] } = useQuery({
    queryKey: ["classroom-subs", classId, "all"],
    queryFn: () => classrooms.submissions(classId).then((r) => r.data),
    refetchInterval: 60000,
  });
  const { data: open = [] } = useQuery({
    queryKey: ["objections", "open"],
    queryFn: () => objections.list({ status: "open", page_size: 200 }).then((r) => r.data.results),
    refetchInterval: 60000,
  });
  const ids = new Set(all.map((s) => s.id));
  const rows: VerdictObjection[] = open.filter((o) => ids.has(o.submission_id));

  return (
    <section className="mb-8">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-2">
        Objections {rows.length > 0 && <span className="text-signal-amber">· {rows.length} open</span>}
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-ink-500">No open objections.</p>
      ) : (
        <div className="divide-y divide-[var(--line-strong)]">
          {rows.map((o) => (
            <Link key={o.id} to={`/results/${o.submission_id}`} state={{ supervising: true }}
              className="grid grid-cols-[1fr_auto] md:grid-cols-12 gap-3 items-center py-3 hover:bg-ink-800/40 px-2 -mx-2 transition-colors">
              <span className="md:col-span-2 text-ink-300 truncate">{o.student}</span>
              <span className="md:col-span-6 min-w-0">
                <span className="block text-ink-50 truncate">{o.submission_title}</span>
                <span className="block text-xs text-ink-500 truncate">{o.reason}</span>
              </span>
              <span className="md:col-span-4 flex items-center justify-end gap-2 font-mono text-[11px] text-ink-400">
                {o.overdue && (
                  <span className="border border-signal-blood/60 text-signal-blood px-1.5 py-0.5 text-[9px] uppercase tracking-[0.14em]">Overdue</span>
                )}
                <span>answer by {new Date(o.due_at).toLocaleDateString()}</span>
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
      toast.success("New join code issued; the old one no longer works");
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
      toast.success("Class year saved; new work is checked against it");
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
      toast.error("Export failed");
    }
  };

  if (!cls) return <p className="text-ink-500">Loading…</p>;

  const filterButtons: [string, string][] = [["flagged", "Flagged"], ["", "All"]];

  return (
    <div>
      <div className="flex items-end justify-between flex-wrap gap-4 mb-6">
        <div>
          <span className="label-mono">Classroom · teacher</span>
          <h1 className="font-display text-4xl text-white mt-2">{cls.name}</h1>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-2 border border-[var(--line-strong)] px-3 py-1.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">join code</span>
            <span className="font-mono tracking-[0.2em] text-ink-50">{cls.join_code}</span>
            <button type="button" aria-label="Copy code" onClick={() => navigator.clipboard.writeText(cls.join_code || "")} className="text-ink-400 hover:text-signal-amber"><Copy size={13} /></button>
            <button type="button" aria-label="New code" onClick={() => rotate.mutate()} className="text-ink-400 hover:text-signal-amber"><RefreshCw size={13} /></button>
          </div>
          <select
            value={cls.level ?? ""}
            onChange={(e) => setLevel.mutate(e.target.value === "" ? null : Number(e.target.value))}
            aria-label="Class year"
            title="Used to check whether vocabulary fits the students' age"
            className="bg-ink-950 border border-[var(--line-strong)] px-2 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-300 focus:border-signal-amber outline-none"
          >
            <option value="">Year not set</option>
            {LEVEL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button type="button" onClick={exportCsv} className={BTN}><Download size={13} /> CSV</button>
          <button type="button" onClick={() => archive.mutate()} className={BTN}><Archive size={13} /> {cls.archived ? "Restore" : "Archive"}</button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-[var(--line-strong)] mb-8">
          {[
            ["Students", String(stats.students)],
            ["Submissions", String(stats.total)],
            ["Flagged", String(stats.flagged)],
            ["Flagged share", `${Math.round(stats.flagged_share * 100)}%`],
          ].map(([label, value]) => (
            <div key={label} className="bg-ink-950 p-4">
              <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{label}</div>
              <div className="font-display text-3xl text-ink-50 mt-1 tabular-nums">{value}</div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-ink-500 mb-6 max-w-2xl">
        Text verdicts come from a language-model check and are indicative only. Treat a flag as a reason to talk to the student, not as proof.
      </p>

      <ObjectionRows classId={id} />

      <div className="grid lg:grid-cols-12 gap-8">
        <section className="lg:col-span-4">
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-2">Students</div>
          {roster.length === 0 ? (
            <p className="text-sm text-ink-500">Share the join code with your students.</p>
          ) : (
            <div className="divide-y divide-[var(--line-strong)]">
              {roster.map((m) => (
                <div key={m.user_id} className="flex items-center gap-3 py-2">
                  <button type="button" onClick={() => setFilter({ student: m.user_id })}
                    className={`flex-1 text-left truncate ${filter.student === m.user_id ? "text-signal-amber" : "text-ink-100 hover:text-ink-50"}`}>
                    {m.username}
                  </button>
                  <span className="font-mono text-[11px] text-ink-500 tabular-nums" title="submissions">{m.total}</span>
                  <span className={`font-mono text-[11px] tabular-nums ${m.flagged ? "text-signal-blood" : "text-ink-600"}`} title="flagged">{m.flagged} flagged</span>
                  <button type="button" aria-label="Take out of class" onClick={() => dropStudent.mutate(m.user_id)} className="text-ink-600 hover:text-signal-blood"><UserMinus size={13} /></button>
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
            {filter.student != null && <span className="text-ink-400">one student</span>}
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
  if (!cls) return <p className="text-ink-500">Loading…</p>;
  return (
    <div>
      <div className="flex items-end justify-between flex-wrap gap-4 mb-6">
        <div>
          <span className="label-mono">Classroom · {cls.owner_name}</span>
          <h1 className="font-display text-4xl text-white mt-2">{cls.name}</h1>
          <p className="text-sm text-ink-400 mt-2">Your teacher sees only what you submit to this class, never your personal checks.</p>
        </div>
        <div className="flex gap-2">
          <Link to="submit" className="border border-signal-amber/60 text-signal-amber px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] hover:bg-signal-amber/10">Submit work</Link>
          <button type="button" onClick={() => exit.mutate()} className="border border-[var(--line-strong)] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400 hover:text-signal-blood">Leave</button>
        </div>
      </div>
      <SubmissionRows rows={rows} showStudent={false} />
    </div>
  );
}

export default function ClassroomDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: cls, isError } = useQuery({ queryKey: ["classroom", id], queryFn: () => classrooms.detail(id!).then((r) => r.data), enabled: !!id });
  if (isError) return <p className="text-ink-500">Classroom not found.</p>;
  if (!cls || !id) return <p className="text-ink-500">Loading…</p>;
  return cls.role === "teacher" ? <TeacherView id={id} /> : <StudentView id={id} />;
}
