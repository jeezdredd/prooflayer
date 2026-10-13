import type { AnalysisResult, Submission } from "../types";

type Evidence = Record<string, unknown>;

function byName(submission: Submission, name: string): AnalysisResult | undefined {
  return submission.analysis_results?.find((r) => r.analyzer_name === name);
}

function Row({ tone, title, children }: { tone: "alert" | "ok" | "muted"; title: string; children?: React.ReactNode }) {
  const dot = tone === "alert" ? "bg-signal-blood" : tone === "ok" ? "bg-signal-sage" : "bg-ink-600";
  return (
    <div className="py-3 grid grid-cols-[auto_1fr] gap-3">
      <span className={`mt-1.5 w-1.5 h-1.5 rounded-full ${dot}`} />
      <div>
        <div className="text-sm text-ink-100">{title}</div>
        {children && <div className="mt-1 text-xs text-ink-400 leading-relaxed">{children}</div>}
      </div>
    </div>
  );
}

function Chips({ items }: { items: string[] }) {
  return (
    <span className="flex flex-wrap gap-1.5 mt-1.5">
      {items.map((w) => (
        <span key={w} className="font-mono text-[11px] px-1.5 py-0.5 border border-[var(--line-strong)] text-ink-200">{w}</span>
      ))}
    </span>
  );
}

export default function TextReport({ submission }: { submission: Submission }) {
  const evasion = byName(submission, "text_evasion");
  const grade = byName(submission, "text_grade_fit");
  const style = byName(submission, "text_style");
  if (!evasion && !grade && !style) return null;

  const ev = (evasion?.evidence ?? {}) as Evidence;
  const gr = (grade?.evidence ?? {}) as Evidence;
  const st = (style?.evidence ?? {}) as Evidence;
  const mixed = (ev.mixed_script_words as string[] | undefined) ?? [];
  const invisible = Object.entries((ev.invisible_characters as Record<string, number> | undefined) ?? {});
  const hidden = (ev.hidden_runs as { text: string; reasons: string[] }[] | undefined) ?? [];
  const beyond = (gr.beyond_level_words as string[] | undefined) ?? [];
  const phrases = Object.keys(((st.phrasebook as Evidence | undefined)?.hits as Record<string, number> | undefined) ?? {});
  const drift = st.drift as { score: number; history_size: number } | undefined;

  return (
    <div className="px-6 py-5 border-b border-ink-700">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-1">Text report</div>
      <p className="text-xs text-ink-500 mb-2">Signals for a conversation with the student, not proof on their own.</p>
      <div className="divide-y divide-[var(--line-strong)]">
        {evasion && (
          evasion.verdict === "fake" || evasion.verdict === "suspicious" ? (
            <Row tone="alert" title="The text was altered to slip past checkers">
              {mixed.length > 0 && <>Words mixing look-alike letters from another alphabet: <Chips items={mixed.slice(0, 12)} /></>}
              {invisible.length > 0 && <div className="mt-1">Invisible characters: {invisible.map(([k, v]) => `${k} × ${v}`).join(", ")}</div>}
              {hidden.length > 0 && <div className="mt-1">Hidden text in the document: {hidden.slice(0, 3).map((h) => `"${h.text}" (${h.reasons.join(", ")})`).join("; ")}</div>}
            </Row>
          ) : (
            <Row tone="ok" title="No character tricks or hidden text" />
          )
        )}
        {grade && (
          grade.verdict === "suspicious" ? (
            <Row tone="alert" title={`Language well above ${String(gr.level_label ?? "the class level")}`}>
              {beyond.length > 0 && <>Words unusual at this age: <Chips items={beyond.slice(0, 14)} /></>}
              {gr.readability_grade != null && <div className="mt-1">Readability is about grade {String(gr.readability_grade)}.</div>}
            </Row>
          ) : gr.reason ? (
            <Row tone="muted" title="Age fit not checked">{gr.reason === "class level not set" ? "Set the class year in class settings to compare vocabulary with the students' age." : String(gr.reason)}</Row>
          ) : (
            <Row tone="ok" title={`Vocabulary fits ${String(gr.level_label ?? "the class level")}`} />
          )
        )}
        {style && (
          style.verdict === "suspicious" ? (
            <Row tone="alert" title="Style differs sharply from this student's earlier work">
              Compared with {drift?.history_size ?? 0} earlier submissions in this class.
            </Row>
          ) : drift ? (
            <Row tone="ok" title="Consistent with this student's earlier work">Compared with {drift.history_size} earlier submissions.</Row>
          ) : (
            <Row tone="muted" title="Style comparison starts after two earlier works from this student" />
          )
        )}
        {phrases.length >= 3 && (
          <Row tone="muted" title="Stock phrases common in chatbot writing">
            <Chips items={phrases.slice(0, 10)} />
          </Row>
        )}
      </div>
    </div>
  );
}
