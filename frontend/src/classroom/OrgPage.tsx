import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, GraduationCap, Plus, RefreshCw, Trash2, UserMinus, Users } from "lucide-react";
import { classrooms, orgs } from "../api/endpoints";
import type { Organization } from "../types";
import { useAuthStore } from "../stores/authStore";
import { toast } from "../components/ui/Toast";
import { ACTION, INPUT, MAIN_URL, SECTION_LABEL, classPath, errorText, levelLabel, levelOptions } from "./shared";
import { AttentionLine, NameField } from "./ClassBits";
import { t, tn } from "../i18n";

function JoinForms({ org }: { org: Organization }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [classCode, setClassCode] = useState("");
  const [name, setName] = useState("");
  const [teacherCode, setTeacherCode] = useState("");
  const [teacherName, setTeacherName] = useState("");
  const needsName = !org.my_name;
  const teacherReady = teacherCode.trim().length === 8 && (!needsName || teacherName.trim().length > 1);
  const classReady = classCode.trim().length === 8 && (!needsName || name.trim().length > 1);

  const joinClass = useMutation({
    mutationFn: () => classrooms.join(classCode.trim(), needsName ? name.trim() : undefined).then((r) => r.data),
    onSuccess: (c) => {
      queryClient.invalidateQueries({ queryKey: ["classroom-hub"] });
      navigate(classPath(c));
    },
    onError: (err) => toast.error(errorText(err, t("Could not join"))),
  });
  const joinTeacher = useMutation({
    mutationFn: () => orgs.joinAsTeacher(org.slug, teacherCode.trim(), needsName ? teacherName.trim() : undefined).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", org.slug] });
      queryClient.invalidateQueries({ queryKey: ["classroom-hub"] });
      toast.success(t("You teach at {name} now", { name: org.name }));
    },
    onError: (err) => toast.error(errorText(err, t("Wrong teacher code"))),
  });

  return (
    <div className="grid md:grid-cols-2 gap-px bg-[var(--line-strong)] mt-8">
      <form className="bg-ink-950 p-5" onSubmit={(e) => { e.preventDefault(); if (classReady) joinClass.mutate(); }}>
        <div className={SECTION_LABEL}>{t("Student · class code from your teacher")}</div>
        {needsName && <NameField value={name} onChange={setName} />}
        <div className="flex gap-2">
          <input value={classCode} onChange={(e) => setClassCode(e.target.value.toUpperCase())} maxLength={8} placeholder={t("CLASS CODE")} className={`${INPUT} font-mono tracking-[0.2em]`} />
          <button type="submit" disabled={!classReady || joinClass.isPending} className={ACTION}>{t("Join")}</button>
        </div>
      </form>
      <form className="bg-ink-950 p-5" onSubmit={(e) => { e.preventDefault(); if (teacherReady) joinTeacher.mutate(); }}>
        <div className={SECTION_LABEL}>{t("Teacher · code from the school admin")}</div>
        {needsName && <NameField value={teacherName} onChange={setTeacherName} teacher />}
        <div className="flex gap-2">
          <input value={teacherCode} onChange={(e) => setTeacherCode(e.target.value.toUpperCase())} maxLength={8} placeholder={t("TEACHER CODE")} className={`${INPUT} font-mono tracking-[0.2em]`} />
          <button type="submit" disabled={!teacherReady || joinTeacher.isPending} className={ACTION}>{t("Join")}</button>
        </div>
      </form>
    </div>
  );
}

function ClassList({ org }: { org: Organization }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [level, setLevel] = useState<number | "">("");
  const canCreate = org.role === "admin" || org.role === "teacher";
  const { data: list = [] } = useQuery({ queryKey: ["org-classes", org.slug], queryFn: () => orgs.classes(org.slug).then((r) => r.data) });
  const create = useMutation({
    mutationFn: () => orgs.createClass(org.slug, name.trim(), level === "" ? null : level).then((r) => r.data),
    onSuccess: (c) => {
      queryClient.invalidateQueries({ queryKey: ["org-classes", org.slug] });
      navigate(classPath(c));
    },
    onError: (err) => toast.error(errorText(err, t("Could not create the class"))),
  });

  const visible = list.filter((c) => !c.archived);
  const archived = list.filter((c) => c.archived);
  const heading = org.role === "admin" ? t("All classes") : t("Your classes");

  return (
    <section>
      <div className={SECTION_LABEL}>{heading}</div>
      {visible.length === 0 ? (
        <p className="text-sm text-ink-500 py-2">{canCreate ? t("No classes yet.") : t("You are not in any class here.")}</p>
      ) : (
        <div className="divide-y divide-[var(--line-strong)]">
          {visible.map((c) => (
            <Link key={c.id} to={classPath(c)} className="grid grid-cols-[auto_1fr_auto] gap-4 items-center py-3 hover:bg-ink-800/40 px-2 -mx-2 transition-colors">
              <GraduationCap size={16} className="text-signal-sage/80" />
              <span className="text-ink-50 min-w-0">
                {c.name} <span className="text-ink-500 text-sm">· {levelLabel(c.level)}</span>
                {org.role !== "student" && <AttentionLine attention={c.attention} />}
              </span>
              <span className="font-mono text-[11px] text-ink-500 flex items-center gap-1.5">
                {org.role === "student"
                  ? t("Teacher: {name}", { name: c.owner_name })
                  : <><Users size={12} /> {c.student_count}{org.role === "admin" && ` · ${c.owner_name}`}</>}
              </span>
            </Link>
          ))}
        </div>
      )}
      {archived.length > 0 && (
        <details className="mt-3">
          <summary className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 cursor-pointer">{t("Archived ({n})", { n: archived.length })}</summary>
          {archived.map((c) => (
            <Link key={c.id} to={classPath(c)} className="block py-2 text-ink-400 hover:text-ink-100">{c.name}</Link>
          ))}
        </details>
      )}
      {canCreate && (
        <form className="flex gap-2 mt-4" onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(); }}>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} placeholder={t("History 10B, spring")} className={INPUT} />
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value === "" ? "" : Number(e.target.value))}
            aria-label={t("Year")}
            className="bg-ink-950 border border-[var(--line-strong)] px-2 text-ink-100 focus:border-signal-amber outline-none"
          >
            <option value="">{t("Year…")}</option>
            {levelOptions().map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button type="submit" disabled={!name.trim() || create.isPending} className={`${ACTION} flex items-center gap-1.5`}><Plus size={13} /> {t("Class")}</button>
        </form>
      )}
    </section>
  );
}

function AdminPanel({ org }: { org: Organization }) {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const { data: teachers = [] } = useQuery({ queryKey: ["org-teachers", org.slug], queryFn: () => orgs.teachers(org.slug).then((r) => r.data) });
  const rotate = useMutation({
    mutationFn: () => orgs.rotateTeacherCode(org.slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", org.slug] });
      toast.success(t("New teacher code issued; the old one no longer works"));
    },
    onError: (err) => toast.error(errorText(err, t("Could not save"))),
  });
  const webSearch = useMutation({
    mutationFn: (enabled: boolean) => orgs.updateSettings(org.slug, { web_search_enabled: enabled }).then((r) => r.data),
    onSuccess: (data) => {
      queryClient.setQueriesData({ queryKey: ["org", org.slug] }, data);
      toast.success(data.web_search_enabled ? t("Web search is on for new work") : t("Web search is off"));
    },
    onError: (err) => toast.error(errorText(err, t("Could not save"))),
  });
  const remove = useMutation({
    mutationFn: (userId: number) => orgs.removeTeacher(org.slug, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["org-teachers", org.slug] }),
    onError: (err) => toast.error(errorText(err, t("Could not remove"))),
  });

  return (
    <section>
      <div className={`${SECTION_LABEL} flex justify-between`}>
        <span>{t("Teachers")}</span>
        {org.teacher_seats ? <span className="tabular-nums">{t("{used} / {total} seats", { used: org.teacher_seats_used ?? 0, total: org.teacher_seats })}</span> : null}
      </div>
      <div className="flex items-center gap-2 border border-[var(--line-strong)] px-3 py-2 mb-4">
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{t("teacher code")}</span>
        <span className="font-mono tracking-[0.2em] text-ink-50 flex-1">{org.teacher_code}</span>
        <button type="button" aria-label={t("Copy code")} onClick={() => navigator.clipboard.writeText(org.teacher_code || "")} className="text-ink-400 hover:text-signal-amber"><Copy size={13} /></button>
        <button type="button" aria-label={t("New code")} title={t("New code")}
          onClick={() => { if (window.confirm(t("Issue a new teacher code? The old code {code} will stop working.", { code: org.teacher_code ?? "" }))) rotate.mutate(); }}
          className="text-ink-400 hover:text-signal-amber"><RefreshCw size={13} /></button>
      </div>
      <p className="text-xs text-ink-500 mb-3">{t("Teachers open this page, enter the code, and create classes under the school plan.")}</p>
      <div className="divide-y divide-[var(--line-strong)]">
        {teachers.map((teacher) => (
          <div key={teacher.user_id} className="flex items-center gap-3 py-2">
            <span className="flex-1 min-w-0">
              <span className="block truncate text-ink-100">{teacher.name}</span>
              {teacher.name !== teacher.username && <span className="block truncate font-mono text-[10px] text-ink-600">{teacher.username}</span>}
            </span>
            <span className="font-mono text-[11px] text-ink-500">{teacher.role === "admin" ? t("admin") : tn(teacher.classes, "{n} class", "{n} classes")}</span>
            {teacher.user_id !== user?.id && teacher.role !== "admin" && (
              <button type="button" aria-label={t("Remove teacher")} title={t("Remove teacher")}
                onClick={() => { if (window.confirm(t("Remove {name} from the school? Their classes stay, but they will not be able to create new ones here.", { name: teacher.name }))) remove.mutate(teacher.user_id); }}
                className="text-ink-600 hover:text-signal-blood"><UserMinus size={13} /></button>
            )}
          </div>
        ))}
      </div>
      <label className="mt-8 flex items-start gap-3 border border-[var(--line-strong)] p-3 cursor-pointer">
        <input
          type="checkbox"
          checked={webSearch.isPending ? !!webSearch.variables : !!org.web_search_enabled}
          disabled={webSearch.isPending}
          onChange={(e) => webSearch.mutate(e.target.checked)}
          className="mt-1 accent-amber-400"
        />
        <span>
          <span className="block text-sm text-ink-100">{t("Search the web for copied passages")}</span>
          <span className="block text-xs text-ink-500 mt-1 leading-relaxed">
            {t("Sends up to 8 sentences from each work to web search and to Wikipedia, and short phrases from them to the open scientific catalogues OpenAlex and arXiv (servers outside Kazakhstan). Finds passages copied from encyclopedias, articles and scientific papers. When it is off, work is compared only with other work in ProofLayer. Reference lists are always checked in open book catalogues (doi.org, OpenAlex, Crossref), whatever this setting says.")}
          </span>
        </span>
      </label>
      {org.plan_active === false && (
        <p className="text-xs text-signal-blood mt-4">
          {t("The Education plan on this school has lapsed: teachers cannot create classes and students cannot submit.")}{" "}
          <a href={`${MAIN_URL}/pricing`} className="underline">{t("Renew")}</a>
        </p>
      )}
      {org.role === "admin" && <DeleteSchool org={org} />}
    </section>
  );
}

function DeleteSchool({ org }: { org: Organization }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirmSlug, setConfirmSlug] = useState("");
  const destroy = useMutation({
    mutationFn: () => orgs.remove(org.slug, password),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["classroom-hub"] });
      toast.success(t("{name} has been deleted", { name: org.name }));
      navigate("/");
    },
    onError: (err) => toast.error(errorText(err, t("Could not delete the school"))),
  });
  const ready = password.length > 0 && confirmSlug.trim() === org.slug && !destroy.isPending;

  return (
    <form
      className="mt-10 border border-signal-blood/40 p-4"
      onSubmit={(e) => { e.preventDefault(); if (ready) destroy.mutate(); }}
    >
      <div className={`${SECTION_LABEL} text-signal-blood`}>{t("Delete school")}</div>
      <p className="text-xs text-ink-400 mb-2">
        {t("This deletes {name}, all of its classes and all work handed in to them. It cannot be undone.", { name: org.name })}
      </p>
      <p className="text-xs text-ink-500 mb-4">
        {t("Deleted data can remain in database backups for up to 14 days, after which the backups expire.")}
      </p>
      <label className="block text-xs text-ink-500 mb-1" htmlFor="delete-school-slug">
        {t("Type")} <span className="font-mono text-ink-100">{org.slug}</span> {t("to confirm")}
      </label>
      <div className="flex mb-3">
        <input
          id="delete-school-slug"
          value={confirmSlug}
          onChange={(e) => setConfirmSlug(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder={org.slug}
          className={`${INPUT} font-mono`}
        />
      </div>
      <label className="block text-xs text-ink-500 mb-1" htmlFor="delete-school-password">{t("Your password")}</label>
      <div className="flex gap-2">
        <input
          id="delete-school-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          className={`${INPUT}`}
        />
        <button
          type="submit"
          disabled={!ready}
          className="border border-signal-blood/60 text-signal-blood px-4 font-mono text-[11px] uppercase tracking-[0.14em] hover:bg-signal-blood/10 disabled:opacity-40 flex items-center gap-1.5"
        >
          <Trash2 size={13} /> {t("Delete")}
        </button>
      </div>
    </form>
  );
}

export default function OrgPage() {
  const { slug = "" } = useParams<{ slug: string }>();
  const { isAuthenticated } = useAuthStore();
  const { data: org, isError } = useQuery({ queryKey: ["org", slug, isAuthenticated], queryFn: () => orgs.detail(slug).then((r) => r.data), retry: false });

  if (isError) return <Navigate to="/" replace />;
  if (!org) return <p className="text-ink-500">{t("Loading…")}</p>;

  return (
    <div>
      <span className="label-mono">classroom.prooflayer.cloud/{org.slug}</span>
      <h1 className="font-display text-5xl text-ink-50 leading-tight mt-2">{org.name}</h1>

      {!isAuthenticated ? (
        <div className="mt-6 max-w-xl">
          <p className="text-ink-400">{t("Sign in to see your classes at {name} or hand in work.", { name: org.name })}</p>
          <div className="flex gap-3 mt-5">
            <Link to={`/login?next=/${org.slug}`} className={`${ACTION} py-2`}>{t("Sign in")}</Link>
            <Link to={`/register?next=/${org.slug}`} className="border border-[var(--line-strong)] px-4 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-300 hover:text-ink-50">{t("Create account")}</Link>
          </div>
        </div>
      ) : org.role === null ? (
        <JoinForms org={org} />
      ) : (
        <div className={`mt-10 grid gap-10 ${org.role === "admin" ? "lg:grid-cols-[2fr_1fr]" : ""}`}>
          <ClassList org={org} />
          {org.role === "admin" && <AdminPanel org={org} />}
        </div>
      )}
    </div>
  );
}
