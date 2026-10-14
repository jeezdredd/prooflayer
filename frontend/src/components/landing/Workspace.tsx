import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import {
  FileSearch, Fingerprint, SearchCheck, Columns2, GraduationCap, Copy, ShieldAlert, Terminal, FolderUp, PenLine, BookCheck, Ghost,
} from "lucide-react";

type GroupId = "investigate" | "teach" | "build";

interface Feature {
  id: string;
  group: GroupId;
  Icon: typeof FileSearch;
  title: string;
  line: string;
  facts: string[];
  to?: string;
  preview: ReactNode;
}

const GROUPS: { id: GroupId; label: string; who: string }[] = [
  { id: "investigate", label: "Investigate", who: "newsrooms, trust & safety, researchers" },
  { id: "teach", label: "Teach", who: "schools and universities" },
  { id: "build", label: "Build", who: "developers and platforms" },
];

const MONO = "font-mono text-[11px] leading-relaxed";
const ROW = "flex items-center justify-between gap-3 py-1.5 border-b border-[var(--line)] last:border-0";

function Pill({ tone, children }: { tone: "blood" | "sage" | "amber" | "ink" | "cyan"; children: ReactNode }) {
  const cls = {
    blood: "text-signal-blood",
    sage: "text-signal-sage",
    amber: "text-signal-amber",
    cyan: "text-signal-cyan",
    ink: "text-ink-400",
  }[tone];
  return (
    <span
      className={`border px-1.5 py-0.5 text-[9px] uppercase tracking-[0.14em] whitespace-nowrap ${cls}`}
      style={{ borderColor: "color-mix(in srgb, currentColor 45%, transparent)" }}
    >
      {children}
    </span>
  );
}

function PreviewHead({ left, right }: { left: string; right?: string }) {
  return (
    <div className="flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.18em] text-ink-500 mb-3">
      <span>{left}</span>
      {right && <span className="text-ink-600">{right}</span>}
    </div>
  );
}

const EVIDENCE = (
  <div className={MONO}>
    <PreviewHead left="Case/2026-0507 · img_4232.png" right="Tribunal 1.6 · fp 9c1e…" />
    {[
      ["Forensics ViT", "0.91", "×3.5", "blood"],
      ["Retrained", "0.88", "×3.5", "blood"],
      ["CLIP Probe", "0.87", "×2.5", "blood"],
      ["ELA", "splice?", "×0.75", "amber"],
      ["Metadata", "stripped", "×1.5", "ink"],
    ].map(([name, vote, weight, tone]) => (
      <div key={name} className={ROW}>
        <span className="text-ink-300">{name}</span>
        <span className="flex items-center gap-3">
          <span className="text-ink-600 tabular-nums">{weight}</span>
          <Pill tone={tone as "blood"}>{vote}</Pill>
        </span>
      </div>
    ))}
    <pre className="mt-3 p-3 bg-ink-950/70 border border-[var(--line)] text-[10px] text-ink-300 overflow-x-auto">
{`{ "analyzer": "clip_probe",
  "ai_probability": 0.87,
  "calibrated": true }`}
    </pre>
    <div className="mt-3 flex gap-2">
      <Pill tone="cyan">Re-analyze with 1.4</Pill>
      <Pill tone="ink">PDF report</Pill>
    </div>
  </div>
);

const PROVENANCE = (
  <div className={MONO}>
    <PreviewHead left="Provenance · press_still.webp" />
    <div className={ROW}><span className="text-ink-300">C2PA manifest</span><Pill tone="ink">none</Pill></div>
    <div className={ROW}><span className="text-ink-300">EXIF capture block</span><Pill tone="amber">removed</Pill></div>
    <div className={ROW}><span className="text-ink-300">Software tag</span><span className="text-ink-500">-</span></div>
    <div className="mt-3 text-[9px] uppercase tracking-[0.16em] text-ink-500">Perceptual-hash matches</div>
    {[
      ["2026-09-14", "1920×1080", "earliest"],
      ["2026-09-15", "1280×720 crop", "re-upload"],
      ["2026-10-02", "1080×1080", "recompressed"],
    ].map(([date, size, tag]) => (
      <div key={date} className={ROW}>
        <span className="text-ink-400 tabular-nums">{date}</span>
        <span className="text-ink-500">{size}</span>
        <Pill tone={tag === "earliest" ? "cyan" : "ink"}>{tag}</Pill>
      </div>
    ))}
  </div>
);

const FACTCHECK = (
  <div className={MONO}>
    <PreviewHead left="Fact-check · article URL" right="3 claims" />
    {[
      ["The bridge opened to traffic in 1932.", "supported", "sage", "3 sources"],
      ["It was the longest arch bridge in Europe.", "contradicted", "blood", "2 sources"],
      ["Over a million people attended.", "unverified", "ink", "0 sources"],
    ].map(([claim, verdict, tone, sources]) => (
      <div key={claim} className="py-2 border-b border-[var(--line)] last:border-0">
        <div className="text-ink-200 font-sans text-[13px] leading-snug">{claim}</div>
        <div className="mt-1.5 flex items-center gap-3">
          <Pill tone={tone as "sage"}>{verdict}</Pill>
          <span className="text-ink-600">{sources}</span>
        </div>
      </div>
    ))}
  </div>
);

const REVIEW = (
  <div className={MONO}>
    <PreviewHead left="Compare · A vs B" />
    <div className="grid grid-cols-2 gap-3">
      {[
        ["A · original.jpg", "0.08", "sage", "authentic"],
        ["B · edited.jpg", "0.64", "amber", "split"],
      ].map(([name, score, tone, verdict]) => (
        <div key={name} className="border border-[var(--line)] p-3">
          <div className="aspect-[4/3] bg-gradient-to-br from-ink-800 to-ink-950 mb-2" />
          <div className="text-ink-400">{name}</div>
          <div className="mt-1 flex items-center justify-between">
            <span className="text-ink-600 tabular-nums">{score}</span>
            <Pill tone={tone as "sage"}>{verdict}</Pill>
          </div>
        </div>
      ))}
    </div>
    <div className="mt-3 flex flex-wrap items-center gap-2 text-ink-400">
      <span>Bench split 3 to 2</span>
      <span className="text-ink-700">→</span>
      <span className="text-signal-amber">review queue</span>
      <span className="text-ink-700">→</span>
      <span>your call retrains</span>
    </div>
  </div>
);

const CLASSROOM = (
  <div className={MONO}>
    <PreviewHead left="classroom.prooflayer.cloud/lyceum-12" right="History 8A" />
    <div className="grid grid-cols-[1.1fr_1.4fr_0.8fr_auto] gap-x-3 text-[9px] uppercase tracking-[0.16em] text-ink-600 pb-1.5 border-b border-[var(--line)]">
      <span>Student</span><span>Fit for grade 8</span><span>Original</span><span>Verdict</span>
    </div>
    {[
      ["A. Petrova", "fits", "96%", "authentic", "sage"],
      ["D. Ivanov", "“декомпозиция”, “синергетический”", "71%", "review", "amber"],
      ["M. Sato", "fits", "88%", "authentic", "sage"],
    ].map(([name, fit, orig, verdict, tone]) => (
      <div key={name} className="grid grid-cols-[1.1fr_1.4fr_0.8fr_auto] gap-x-3 items-center py-1.5 border-b border-[var(--line)] last:border-0">
        <span className="text-ink-200">{name}</span>
        <span className={fit === "fits" ? "text-ink-500" : "text-signal-amber"}>{fit}</span>
        <span className="text-ink-400 tabular-nums">{orig}</span>
        <Pill tone={tone as "sage"}>{verdict}</Pill>
      </div>
    ))}
    <div className="mt-3 text-ink-500">Style drift vs. own earlier work: <span className="text-signal-amber">0.74</span> for D. Ivanov</div>
    <div className="mt-1 text-ink-500">Radar: <span className="text-signal-amber">3 essays share one skeleton</span>, 84% of sentences aligned in order</div>
  </div>
);

const WRITING = (
  <div className={MONO}>
    <PreviewHead left="AI writing · essay_ru.docx" right="ru · 1,240 tokens" />
    {[
      ["window 1", 0.93, "blood"],
      ["window 2", 0.88, "blood"],
      ["window 3", 0.41, "ink"],
    ].map(([label, p, tone]) => (
      <div key={label as string} className={ROW}>
        <span className="text-ink-400">{label}</span>
        <span className="flex items-center gap-3 flex-1 justify-end">
          <span className="h-1 bg-[var(--line)] w-28 relative">
            <span className={`absolute inset-y-0 left-0 ${tone === "blood" ? "bg-signal-blood" : "bg-ink-500"}`} style={{ width: `${(p as number) * 100}%` }} />
          </span>
          <span className="text-ink-300 tabular-nums w-8 text-right">{(p as number).toFixed(2)}</span>
        </span>
      </div>
    ))}
    <div className="mt-3 flex flex-wrap items-center gap-2 text-ink-400">
      <span>above 99% of human essays</span>
      <span className="text-ink-700">→</span>
      <Pill tone="amber">flag</Pill>
      <span className="text-ink-700">+ anti-bypass hit →</span>
      <Pill tone="blood">synthetic</Pill>
    </div>
  </div>
);

const SOURCES = (
  <div className={MONO}>
    <PreviewHead left="Sources · referat.docx" right="реферат / доклад" />
    {[
      ["DOI 10.1038/nature14539", "exists", "sage"],
      ["DOI 10.1038/nature99999123", "not registered", "blood"],
      ["Petrov, A. (2021). Neural gardening...", "no such work", "blood"],
      ["Выготский, Л. С. Мышление и речь", "exists", "sage"],
    ].map(([ref, status, tone]) => (
      <div key={ref} className={ROW}>
        <span className="text-ink-300 truncate">{ref}</span>
        <Pill tone={tone as "sage"}>{status}</Pill>
      </div>
    ))}
    <div className="mt-3 text-ink-400">
      Reference list: <span className="text-ink-200">APA 7</span>, 2 issues: <span className="text-signal-amber">use &amp; before the last author</span>, <span className="text-signal-amber">not in alphabetical order</span>
    </div>
  </div>
);

const SHADOW = (
  <div className={MONO}>
    <PreviewHead left="Assignment shadow · 9B" right="8 AI answers" />
    <div className="text-ink-500 mb-2">Нужно ли читать книги в эпоху интернета?</div>
    {[
      ["Books build imagination in a way screens rarely do.", "Книги развивают воображение так, как экраны не умеют."],
      ["Reading every day grows the vocabulary for exams.", "Ежедневное чтение расширяет словарный запас."],
    ].map(([ai, student]) => (
      <div key={ai} className="py-1.5 border-b border-[var(--line)] last:border-0">
        <div className="text-ink-200 font-sans text-[12px]">{student}</div>
        <div className="text-ink-600">AI: {ai}</div>
      </div>
    ))}
    <div className="mt-3 flex items-center gap-2 text-ink-400">
      <span>62% of sentences, same order</span>
      <span className="text-ink-700">→</span>
      <Pill tone="amber">review</Pill>
    </div>
  </div>
);

const ORIGINALITY = (
  <div className={MONO}>
    <PreviewHead left="Originality · essay.docx" right="66% original" />
    <p className="font-sans text-[13px] leading-relaxed text-ink-300">
      The industrial revolution changed how cities grew.{" "}
      <span className="text-ink-50 px-0.5 border-b border-signal-amber" style={{ background: "rgba(245, 176, 66, 0.16)" }}>Factories drew workers from the countryside, and housing could not keep pace</span>
      , which led to crowded districts.{" "}
      <span className="text-ink-50 px-0.5 border-b border-signal-cyan" style={{ background: "rgba(34, 211, 238, 0.14)" }}>Reformers later pushed for sanitation laws</span>.
    </p>
    <div className="mt-3">
      <div className={ROW}><span className="text-ink-300">en.wikipedia.org</span><span className="flex gap-2 items-center"><span className="text-ink-600">exact</span><Pill tone="amber">18%</Pill></span></div>
      <div className={ROW}><span className="text-ink-300">ru source, translated</span><span className="flex gap-2 items-center"><span className="text-ink-600">meaning</span><Pill tone="cyan">9%</Pill></span></div>
      <div className={ROW}><span className="text-ink-300">classmate, same class</span><span className="flex gap-2 items-center"><span className="text-ink-600">exact</span><Pill tone="amber">7%</Pill></span></div>
    </div>
  </div>
);

const BYPASS = (
  <div className={MONO}>
    <PreviewHead left="Anti-bypass · report.docx" right="altered" />
    <div className="font-sans text-[15px] text-ink-200 leading-relaxed">
      Эта работа н<span className="text-signal-blood underline decoration-dotted underline-offset-4">a</span>писана сам
      <span className="text-signal-blood underline decoration-dotted underline-offset-4">o</span>стоятельно
      <span className="text-signal-blood font-mono text-[10px] align-super">⟨ZWSP⟩</span>.
    </div>
    <div className="mt-3">
      <div className={ROW}><span className="text-ink-300">Latin letters in Cyrillic words</span><Pill tone="blood">2</Pill></div>
      <div className={ROW}><span className="text-ink-300">Zero-width characters</span><Pill tone="blood">14</Pill></div>
      <div className={ROW}><span className="text-ink-300">Hidden DOCX run, white, 1pt</span><Pill tone="blood">1</Pill></div>
    </div>
  </div>
);

const API = (
  <div className={MONO}>
    <PreviewHead left="REST · webhook" />
    <pre className="p-3 bg-ink-950/70 border border-[var(--line)] text-[10px] text-ink-300 overflow-x-auto leading-relaxed">
<span className="text-signal-violet">curl</span>{` -H "Authorization: Api-Key pl_••••" \\
  -F file=@essay.pdf \\
  https://api.prooflayer.cloud/api/v1/content/submissions/`}
    </pre>
    <pre className="mt-3 p-3 bg-ink-950/70 border border-[var(--line)] text-[10px] text-ink-300 overflow-x-auto leading-relaxed">
<span className="text-ink-500">POST https://you.example/hook</span>{`
X-ProofLayer-Signature: sha256=4f1c…
{ "verdict": "fake", "score": 0.87,
  "tribunal_version": "1.6" }`}
    </pre>
  </div>
);

const BATCH = (
  <div className={MONO}>
    <PreviewHead left="Batch · term-papers.zip" right="42 files" />
    {[
      ["essay_01.docx", "0.12", "authentic", "sage"],
      ["essay_02.pdf", "0.91", "synthetic", "blood"],
      ["essay_03.docx", "0.47", "inconclusive", "ink"],
      ["scan_04.jpg", "", "running", "cyan"],
    ].map(([file, score, verdict, tone]) => (
      <div key={file} className={ROW}>
        <span className="text-ink-300">{file}</span>
        <span className="flex items-center gap-3">
          <span className="text-ink-600 tabular-nums">{score}</span>
          <Pill tone={tone as "sage"}>{verdict}</Pill>
        </span>
      </div>
    ))}
    <div className="mt-3"><Pill tone="ink">export.csv</Pill></div>
  </div>
);

const FEATURES: Feature[] = [
  {
    id: "evidence", group: "investigate", Icon: FileSearch, title: "Evidence report", to: "/upload",
    line: "Every verdict arrives with what each judge saw, not a single opaque score.",
    facts: ["Raw JSON evidence and the vote weight of every analyzer", "Stamped with the Tribunal version that judged it; re-run with the current one", "PDF report for editors and case files"],
    preview: EVIDENCE,
  },
  {
    id: "provenance", group: "investigate", Icon: Fingerprint, title: "Provenance trail", to: "/upload",
    line: "Where a file came from before it reached you.",
    facts: ["C2PA Content Credentials and EXIF down to the capture block", "Perceptual hashes find re-uploads, crops and recompressions", "The earliest copy we have seen is marked"],
    preview: PROVENANCE,
  },
  {
    id: "factcheck", group: "investigate", Icon: SearchCheck, title: "Fact-check", to: "/factcheck",
    line: "Claims pulled out of text, an article URL, a PDF or a DOCX and checked against live sources.",
    facts: ["One verdict per claim, each with linked sources", "Paste text, drop a document or give a URL", "Export the checked claims"],
    preview: FACTCHECK,
  },
  {
    id: "review", group: "investigate", Icon: Columns2, title: "Compare and human review", to: "/compare",
    line: "Two files judge by judge, and a person for the cases machines split on.",
    facts: ["Side-by-side scores for an original and an edit", "Split benches go to a reviewer instead of being averaged", "Reviewer corrections retrain our detector"],
    preview: REVIEW,
  },
  {
    id: "classroom", group: "teach", Icon: GraduationCap, title: "Classroom", to: "/pricing",
    line: "Your school's own space: students only hand in work and see their results, the tools stay with teachers.",
    facts: ["Class level from grade 1 to university year 6", "Vocabulary checked against the grade and against the student's own level, so strong students are not flagged", "Personal comparisons wait for three earlier works: no verdict from one or two", "Class radar: essays built on one skeleton and sudden jumps in a student's level"],
    preview: CLASSROOM,
  },
  {
    id: "writing", group: "teach", Icon: PenLine, title: "AI writing check", to: "/pricing",
    line: "A classifier trained on human and machine writing in ru, en and fr, humanized rewrites included.",
    facts: ["Flags 91-100% of AI text on held-out sets, including a model it never saw", "2-4% of human essays get a flag, none get convicted by it alone", "Every passage gets its own score, so a pasted section stands out"],
    preview: WRITING,
  },
  {
    id: "shadow", group: "teach", Icon: Ghost, title: "Assignment shadow", to: "/pricing",
    line: "Paste your assignment and we answer it with AI the way students of different ages would.",
    facts: ["Every work in the class is compared with those answers sentence by sentence", "Rewording does not hide an argument that follows the AI answer in the same order", "The matching sentences are shown side by side"],
    preview: SHADOW,
  },
  {
    id: "originality", group: "teach", Icon: Copy, title: "Originality check", to: "/pricing",
    line: "Plagiarism checked on every upload, across the class, the school and the open web.",
    facts: ["Fingerprints of five-word sequences catch copied passages", "Meaning matches catch paraphrase and translation in ru, en, fr", "Sources listed with the matching spans highlighted"],
    preview: ORIGINALITY,
  },
  {
    id: "sources", group: "teach", Icon: BookCheck, title: "Sources and format", to: "/pricing",
    line: "Every DOI, ISBN, arXiv id, link and reference checked against real catalogues, and the list checked against its style.",
    facts: ["Invented sources, a common chatbot trace, are listed one by one", "APA, MLA, Chicago, Harvard, IEEE, Vancouver, ГОСТ and ISO 690 formatting", "Knows an essay from a retelling or a report, so a story without sources is not a problem"],
    preview: SOURCES,
  },
  {
    id: "bypass", group: "teach", Icon: ShieldAlert, title: "Anti-bypass", to: "/pricing",
    line: "The tricks that fool other checkers count as evidence here.",
    facts: ["Latin letters hidden in Cyrillic words, and the reverse", "Invisible characters and unusual spaces", "Hidden, white or 1pt text inside DOCX files"],
    preview: BYPASS,
  },
  {
    id: "api", group: "build", Icon: Terminal, title: "API keys and webhooks", to: "/developers",
    line: "Everything in the dashboard is available over REST.",
    facts: ["Keys shown once, revocable, with per-key rate limits", "Signed webhook when a verdict is ready (HMAC-SHA256)", "OpenAPI reference at api.prooflayer.cloud/api/docs"],
    preview: API,
  },
  {
    id: "batch", group: "build", Icon: FolderUp, title: "Batch upload", to: "/upload",
    line: "Many files or one ZIP in a single request.",
    facts: ["Live status for every file", "CSV export of verdicts and scores", "ZIP limits guard against archive bombs"],
    preview: BATCH,
  },
];

export default function Workspace() {
  const [group, setGroup] = useState<GroupId>("investigate");
  const [selected, setSelected] = useState("evidence");
  const list = FEATURES.filter((f) => f.group === group);
  const active = FEATURES.find((f) => f.id === selected && f.group === group) ?? list[0];

  return (
    <div>
      <div className="flex flex-wrap gap-x-8 gap-y-3 border-b border-[var(--line-strong)]" role="tablist">
        {GROUPS.map((g) => {
          const on = g.id === group;
          return (
            <button
              key={g.id}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => {
                setGroup(g.id);
                setSelected(FEATURES.find((f) => f.group === g.id)!.id);
              }}
              className="relative pb-3 text-left group"
            >
              <span className={`font-display text-2xl transition-colors ${on ? "text-ink-50" : "text-ink-400 group-hover:text-ink-100"}`}>{g.label}</span>
              <span className="block font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500 mt-0.5">{g.who}</span>
              {on && <motion.span layoutId="workspace-tab" className="absolute left-0 right-0 -bottom-px h-px bg-signal-amber" />}
            </button>
          );
        })}
      </div>

      <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] gap-8 lg:gap-12 mt-8">
        <div className="divide-y divide-[var(--line)]">
          {list.map((f) => {
            const on = f.id === active.id;
            const Icon = f.Icon;
            return (
              <div key={f.id} className="py-5">
                <button
                  type="button"
                  onClick={() => setSelected(f.id)}
                  onMouseEnter={() => setSelected(f.id)}
                  aria-expanded={on}
                  className="w-full text-left group grid grid-cols-[auto_1fr] gap-4"
                >
                  <span className={`mt-1 transition-colors ${on ? "text-signal-amber" : "text-ink-600 group-hover:text-ink-300"}`}>
                    <Icon size={18} strokeWidth={1.5} />
                  </span>
                  <span>
                    <span className={`block font-display text-2xl leading-tight transition-colors ${on ? "text-ink-50" : "text-ink-300 group-hover:text-ink-100"}`}>{f.title}</span>
                    <span className="block text-sm text-ink-400 mt-1.5 leading-relaxed">{f.line}</span>
                  </span>
                </button>
                <AnimatePresence initial={false}>
                  {on && (
                    <motion.div
                      key="facts"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25 }}
                      className="overflow-hidden pl-[34px]"
                    >
                      <ul>
                        {f.facts.map((fact) => (
                          <li key={fact} className="flex gap-2.5 text-sm text-ink-300 mt-2 first:mt-3">
                            <span className="text-signal-amber font-mono text-xs mt-0.5">+</span>
                            {fact}
                          </li>
                        ))}
                      </ul>
                      <div className="lg:hidden mt-4 case-card p-4">{f.preview}</div>
                      {f.to && (
                        <Link to={f.to} className="lg:hidden inline-block mt-3 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-400 hover:text-signal-amber">
                          Open {f.title.toLowerCase()} →
                        </Link>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>

        <div className="hidden lg:block lg:sticky lg:top-24 self-start">
          <div className="case-card crop-marks p-5 sm:p-6 min-h-[340px]">
            <AnimatePresence mode="wait">
              <motion.div
                key={active.id}
                initial={{ opacity: 0, y: 8, filter: "blur(4px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, y: -8, filter: "blur(4px)" }}
                transition={{ duration: 0.25 }}
              >
                {active.preview}
              </motion.div>
            </AnimatePresence>
          </div>
          {active.to && (
            <Link to={active.to} className="inline-block mt-4 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-400 hover:text-signal-amber transition-colors">
              Open {active.title.toLowerCase()} →
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
