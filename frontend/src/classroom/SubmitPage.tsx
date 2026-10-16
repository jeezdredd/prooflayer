import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import UploadForm from "../components/UploadForm";
import { batches, classrooms, content } from "../api/endpoints";
import { toast } from "../components/ui/Toast";
import { classPath, INPUT } from "./shared";
import { t, tn } from "../i18n";

function failureText(err: unknown, fallback: string): string {
  const res = (err as { response?: { status?: number; data?: { detail?: string; files?: string[]; file?: string[] } } })?.response;
  const detail = res?.data?.detail || res?.data?.files?.[0] || res?.data?.file?.[0];
  return detail ? t(detail) : fallback;
}

export default function SubmitPage() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const [progress, setProgress] = useState<number | null>(null);
  const [student, setStudent] = useState<number | null>(Number(params.get("student")) || null);
  const { data: cls } = useQuery({ queryKey: ["classroom", id], queryFn: () => classrooms.detail(id).then((r) => r.data) });
  const teacher = cls?.role === "teacher";
  const { data: roster = [] } = useQuery({
    queryKey: ["classroom-roster", id],
    queryFn: () => classrooms.roster(id).then((r) => r.data),
    enabled: teacher,
  });
  const studentName = roster.find((m) => m.user_id === student)?.username;

  const done = () => {
    queryClient.invalidateQueries({ queryKey: ["classroom-subs", id] });
    queryClient.invalidateQueries({ queryKey: ["classroom-roster", id] });
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

  const sendMany = async (files: File[]) => {
    setProgress(0);
    try {
      const res = await batches.create(files, "", id, teacher ? student : null);
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
            {t("Upload any work yourself: a scanned page, an email attachment, an essay from another platform. Pick the student so it joins their history and the style comparison with their earlier work.")}
          </p>
          <label className="block mb-8 max-w-md">
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("Whose work is this?")}</span>
            <select
              value={student ?? ""}
              onChange={(e) => setStudent(e.target.value ? Number(e.target.value) : null)}
              className={`${INPUT} w-full mt-2 bg-ink-950`}
            >
              <option value="">{t("No student, just check it")}</option>
              {roster.map((m) => <option key={m.user_id} value={m.user_id}>{m.username}</option>)}
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
          <p className="text-ink-400 mt-2 mb-8">
            {t("Essays as PDF, DOCX or plain text; images, audio and video too. {teacher} sees what you hand in here and the verdict on it.", { teacher: cls.owner_name })}
          </p>
        </>
      )}
      <UploadForm onFileSelect={sendOne} onBatchSelect={sendMany} disabled={progress !== null} />
      {progress !== null && (
        <div className="mt-4 h-px bg-[var(--line-strong)] relative overflow-hidden">
          <div className="absolute inset-y-0 left-0 bg-signal-amber transition-[width] duration-300" style={{ width: `${progress}%` }} />
        </div>
      )}
    </div>
  );
}
