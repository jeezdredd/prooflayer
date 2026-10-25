import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import UploadForm from "../components/UploadForm";
import { batches, classrooms, content } from "../api/endpoints";
import { toast } from "../components/ui/Toast";
import { ACTION, classPath, INPUT, SECTION_LABEL } from "./shared";
import { locale, t, tn } from "../i18n";
import type { ClassMember } from "../types";

function failureText(err: unknown, fallback: string): string {
  const res = (err as { response?: { status?: number; data?: { detail?: string; files?: string[]; file?: string[] } } })?.response;
  const detail = res?.data?.detail || res?.data?.files?.[0] || res?.data?.file?.[0];
  return detail ? t(detail) : fallback;
}

function plain(value: string): string {
  return value.toLowerCase().replace(/ё/g, "е");
}

function isArchive(file: File): boolean {
  return file.name.toLowerCase().endsWith(".zip");
}

function guessStudent(fileName: string, roster: ClassMember[]): number | null {
  const name = plain(fileName);
  const hits = roster.filter((m) =>
    plain(m.name)
      .split(/[\s.,_-]+/)
      .filter((part) => part.length >= 4)
      .some((part) => name.includes(part.length >= 5 ? part.slice(0, -1) : part)),
  );
  return hits.length === 1 ? hits[0].user_id : null;
}

export default function SubmitPage() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const [progress, setProgress] = useState<number | null>(null);
  const [student, setStudent] = useState<number | null>(Number(params.get("student")) || null);
  const [batchName, setBatchName] = useState("");
  const [pending, setPending] = useState<File[] | null>(null);
  const [owners, setOwners] = useState<Record<string, number | null>>({});
  const { data: cls } = useQuery({ queryKey: ["classroom", id], queryFn: () => classrooms.detail(id).then((r) => r.data) });
  const teacher = cls?.role === "teacher";
  const { data: roster = [] } = useQuery({
    queryKey: ["classroom-roster", id],
    queryFn: () => classrooms.roster(id).then((r) => r.data),
    enabled: teacher,
  });
  const studentName = roster.find((m) => m.user_id === student)?.name;

  const done = () => {
    queryClient.invalidateQueries({ queryKey: ["classroom-subs", id] });
    queryClient.invalidateQueries({ queryKey: ["classroom-roster", id] });
    queryClient.invalidateQueries({ queryKey: ["classroom-batches", id] });
    setProgress(null);
  };

  const sendOne = async (file: File) => {
    setProgress(0);
    try {
      const res = await content.upload(file, setProgress, id, teacher ? student : null);
      toast.success(teacher ? t("{name} is being checked", { name: file.name }) : t("{name} handed in", { name: file.name }));
      navigate(`/results/${res.data.id}`, { state: { supervising: teacher && !!student } });
    } catch (err) {
      toast.error(failureText(err, t("Upload failed")));
    } finally {
      done();
    }
  };

  const chooseMany = (files: File[]) => {
    if (!teacher) {
      void sendMany(files, {});
      return;
    }
    setOwners(Object.fromEntries(files.filter((f) => !isArchive(f)).map((f) => [f.name, guessStudent(f.name, roster) ?? student])));
    setPending(files);
  };

  const sendMany = async (files: File[], assigned: Record<string, number | null>) => {
    setPending(null);
    setProgress(0);
    try {
      const name = batchName.trim() || t("Upload of {date}", { date: new Date().toLocaleDateString(locale()) });
      const res = await batches.create(files, name, id, teacher ? student : null, assigned);
      const skipped = res.data.skipped.length;
      toast.success(tn(res.data.summary.total, "{n} file handed in", "{n} files handed in") + (skipped ? t(", {n} skipped", { n: skipped }) : ""));
      navigate(`/batches/${res.data.id}`);
    } catch (err) {
      toast.error(failureText(err, t("Upload failed")));
    } finally {
      done();
    }
  };

  if (!cls) return <p className="text-ink-500">{t("Loading…")}</p>;

  return (
    <div className="max-w-3xl">
      <Link to={classPath(cls)} className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-400 hover:text-ink-100">
        <ArrowLeft size={13} /> {cls.name}
      </Link>
      {teacher ? (
        <>
          <h1 className="font-display text-4xl text-ink-50 mt-4">{t("Check work")}</h1>
          <p className="text-ink-400 mt-2 mb-6">
            {t("Upload any work yourself: a DOCX or PDF file with text, an email attachment, an essay from another platform. Pick the student so it joins their history and the style comparison with their earlier work.")}
          </p>
          <p className="text-xs text-ink-500 -mt-4 mb-6 max-w-2xl">
            {t("A photo or scan of a handwritten page is not read as text yet: it is checked like a picture. Type the text or upload a PDF with selectable text.")}
          </p>
          <label className="block mb-6 max-w-md">
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("Whose work is this?")}</span>
            <select
              value={student ?? ""}
              onChange={(e) => setStudent(e.target.value ? Number(e.target.value) : null)}
              className={`${INPUT} w-full mt-2 bg-ink-950`}
            >
              <option value="">{t("No student, just check it")}</option>
              {roster.map((m) => <option key={m.user_id} value={m.user_id}>{m.name}</option>)}
            </select>
            <span className="block text-xs text-ink-500 mt-2">
              {studentName
                ? t("{name} will see this work and its verdict, like anything they hand in.", { name: studentName })
                : t("Not linked to any student. It counts towards the class plan.")}
            </span>
          </label>
        </>
      ) : (
        <>
          <h1 className="font-display text-4xl text-ink-50 mt-4">{t("Hand in work")}</h1>
          <p className="text-ink-400 mt-2 mb-6">
            {t("Essays as PDF, DOCX or plain text; images, audio and video too. {teacher} sees what you hand in here and the verdict on it.", { teacher: cls.owner_name })}
          </p>
        </>
      )}
      <label className="block mb-8 max-w-md">
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("Name for several files (optional)")}</span>
        <input
          value={batchName}
          onChange={(e) => setBatchName(e.target.value)}
          maxLength={120}
          placeholder={t("For example, Test 8A, 12.10")}
          className={`${INPUT} w-full mt-2`}
        />
        <span className="block text-xs text-ink-500 mt-2">{t("Used when you upload several files at once, so the set is easy to find later.")}</span>
      </label>
      {pending ? (
        <div className="border border-[var(--line-strong)] p-4">
          <div className={SECTION_LABEL}>{t("Whose work is each file?")}</div>
          <p className="text-xs text-ink-500">{t("Files named after a student are matched to them. Check the list before sending.")}</p>
          <div className="mt-3 divide-y divide-[var(--line-strong)]">
            {pending.map((f, i) => (
              <div key={`${f.name}-${i}`} className="flex flex-col sm:flex-row sm:items-center gap-2 py-2">
                <span className="text-sm text-ink-100 truncate sm:flex-1 min-w-0">{f.name}</span>
                {isArchive(f) ? (
                  <span className="text-xs text-ink-500 sm:w-64">{t("Files inside the archive go to the student chosen above.")}</span>
                ) : (
                  <select
                    aria-label={t("Whose work is this?")}
                    value={owners[f.name] ?? ""}
                    onChange={(e) => setOwners({ ...owners, [f.name]: e.target.value ? Number(e.target.value) : null })}
                    className={`${INPUT} sm:flex-none sm:w-64 bg-ink-950`}
                  >
                    <option value="">{t("No student, just check it")}</option>
                    {roster.map((m) => <option key={m.user_id} value={m.user_id}>{m.name}</option>)}
                  </select>
                )}
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-3 mt-4">
            <button type="button" onClick={() => void sendMany(pending, owners)} className={`${ACTION} py-2`}>
              {tn(pending.length, "Check {n} file", "Check {n} files")}
            </button>
            <button type="button" onClick={() => setPending(null)} className="px-4 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-400 hover:text-ink-100">
              {t("Cancel")}
            </button>
          </div>
        </div>
      ) : (
        <UploadForm onFileSelect={sendOne} onBatchSelect={chooseMany} disabled={progress !== null} />
      )}
      {progress !== null && (
        <div className="mt-4 h-px bg-[var(--line-strong)] relative overflow-hidden">
          <div className="absolute inset-y-0 left-0 bg-signal-amber transition-[width] duration-300" style={{ width: `${progress}%` }} />
        </div>
      )}
    </div>
  );
}
