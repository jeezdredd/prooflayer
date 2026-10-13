import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { objections } from "../api/endpoints";
import { useAuthStore } from "../stores/authStore";
import type { ObjectionDecision, Submission, VerdictObjection } from "../types";

const MIN_LENGTH = 10;
const LABEL = "font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500";
const FIELD = "w-full bg-transparent border border-[var(--line-strong)] px-3 py-2 text-sm text-ink-50 focus:border-signal-amber outline-none";
const ACTION = "border border-signal-amber/60 text-signal-amber px-4 py-2 font-mono text-[11px] uppercase tracking-[0.14em] hover:bg-signal-amber/10 disabled:opacity-40";

const DECISION_LABEL: Record<ObjectionDecision, string> = {
  upheld: "Assessment upheld",
  changed: "Assessment changed",
};

function errorInfo(err: unknown): { status?: number; message: string } {
  const response = (err as { response?: { status?: number; data?: Record<string, unknown> } })?.response;
  const data = response?.data;
  let message = "Could not send. Please try again.";
  if (data && typeof data.detail === "string") message = data.detail;
  else if (data) {
    const first = Object.values(data)[0];
    if (Array.isArray(first) && first.length) message = String(first[0]);
  }
  return { status: response?.status, message };
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleDateString() : "";
}

function useStoreObjection(submissionId: string) {
  const queryClient = useQueryClient();
  return (objection: VerdictObjection) =>
    queryClient.setQueryData(["submission", submissionId], (old: Submission | undefined) =>
      old ? { ...old, objection } : old,
    );
}

function ObjectionStatus({ objection }: { objection: VerdictObjection }) {
  const answered = objection.status === "answered";
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`font-mono text-[10px] uppercase tracking-[0.14em] border px-2 py-0.5 ${answered ? "border-signal-sage/50 text-signal-sage" : "border-signal-amber/50 text-signal-amber"}`}>
          {answered ? "Answered" : "Open"}
        </span>
        {!answered && objection.overdue && (
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] border border-signal-blood/60 text-signal-blood px-2 py-0.5">Overdue</span>
        )}
        <span className="font-mono text-[11px] text-ink-500">
          sent {formatDate(objection.created_at)} by {objection.student}
          {!answered && ` · answer due by ${formatDate(objection.due_at)}`}
        </span>
      </div>
      <p className="text-sm text-ink-300 whitespace-pre-wrap">{objection.reason}</p>
      {answered && (
        <div className="border-l-2 border-signal-sage/50 pl-3">
          <div className="text-sm text-ink-100">
            {objection.decision ? DECISION_LABEL[objection.decision] : "Answered"}
            <span className="font-mono text-[11px] text-ink-500"> · {formatDate(objection.responded_at)}</span>
          </div>
          <p className="text-sm text-ink-300 mt-1 whitespace-pre-wrap">{objection.response}</p>
        </div>
      )}
    </div>
  );
}

function RespondForm({ objection, submissionId }: { objection: VerdictObjection; submissionId: string }) {
  const store = useStoreObjection(submissionId);
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState<ObjectionDecision>("upheld");
  const [text, setText] = useState("");
  const respond = useMutation({
    mutationFn: () => objections.respond(objection.id, decision, text.trim()).then((r) => r.data),
    onSuccess: (data) => {
      store(data);
      queryClient.invalidateQueries({ queryKey: ["objections"] });
    },
  });
  const ready = text.trim().length >= MIN_LENGTH && !respond.isPending;

  return (
    <form
      className="mt-5 space-y-3 border-t border-[var(--line-strong)] pt-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) respond.mutate();
      }}
    >
      <div className={LABEL}>Your answer</div>
      <div className="flex gap-4 text-sm text-ink-200">
        {(["upheld", "changed"] as ObjectionDecision[]).map((value) => (
          <label key={value} className="flex items-center gap-2 cursor-pointer">
            <input type="radio" name="objection-decision" value={value} checked={decision === value} onChange={() => setDecision(value)} />
            {DECISION_LABEL[value]}
          </label>
        ))}
      </div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={4}
        maxLength={2000}
        placeholder="Explain your decision to the student (at least 10 characters)"
        className={FIELD}
      />
      {respond.isError && <p className="text-xs text-signal-blood">{errorInfo(respond.error).message}</p>}
      <button type="submit" disabled={!ready} className={ACTION}>
        {respond.isPending ? "Sending…" : "Send answer"}
      </button>
    </form>
  );
}

function CreateForm({ submissionId }: { submissionId: string }) {
  const store = useStoreObjection(submissionId);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [blocked, setBlocked] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => objections.create(submissionId, reason.trim()).then((r) => r.data),
    onSuccess: (data) => store(data),
    onError: (err) => {
      const info = errorInfo(err);
      if (info.status === 403) setBlocked(info.message);
    },
  });
  const ready = reason.trim().length >= MIN_LENGTH && !create.isPending;

  if (blocked) return <p className="text-sm text-ink-500">{blocked}</p>;
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className={ACTION}>
        Object to this assessment
      </button>
    );
  }
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) create.mutate();
      }}
    >
      <p className="text-sm text-ink-400 leading-relaxed">
        Tell your teacher or our reviewers why you think the assessment is wrong. A person reads every objection and answers it.
      </p>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={4}
        maxLength={2000}
        placeholder="Why do you disagree? (at least 10 characters)"
        className={FIELD}
      />
      {create.isError && <p className="text-xs text-signal-blood">{errorInfo(create.error).message}</p>}
      <div className="flex gap-3">
        <button type="submit" disabled={!ready} className={ACTION}>
          {create.isPending ? "Sending…" : "Send objection"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500 hover:text-ink-200">
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function ObjectionPanel({ submission, supervising }: { submission: Submission; supervising: boolean }) {
  const { user } = useAuthStore();
  if (submission.status !== "completed") return null;
  const objection = submission.objection ?? null;
  if (!objection && supervising) return null;
  const isAuthor = !!objection && objection.student === user?.username;

  return (
    <section className="case-card p-6 mt-4">
      <h4 className="label-mono mb-3">Objection</h4>
      {objection ? (
        <>
          <ObjectionStatus objection={objection} />
          {objection.status === "open" && !isAuthor && <RespondForm objection={objection} submissionId={submission.id} />}
        </>
      ) : (
        <CreateForm submissionId={submission.id} />
      )}
    </section>
  );
}
