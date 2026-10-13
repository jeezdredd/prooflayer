import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, GraduationCap, Plus, RefreshCw, Trash2, UserMinus, Users } from "lucide-react";
import { classrooms, orgs } from "../api/endpoints";
import type { Organization } from "../types";
import { useAuthStore } from "../stores/authStore";
import { toast } from "../components/ui/Toast";
import { ACTION, INPUT, LEVEL_OPTIONS, MAIN_URL, SECTION_LABEL, classPath, errorText, levelLabel } from "./shared";

function JoinForms({ org }: { org: Organization }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [classCode, setClassCode] = useState("");
  const [teacherCode, setTeacherCode] = useState("");

  const joinClass = useMutation({
    mutationFn: () => classrooms.join(classCode.trim()).then((r) => r.data),
    onSuccess: (c) => {
      queryClient.invalidateQueries({ queryKey: ["classroom-hub"] });
      navigate(classPath(c));
    },
    onError: (err) => toast.error(errorText(err, "Could not join")),
  });
  const joinTeacher = useMutation({
    mutationFn: () => orgs.joinAsTeacher(org.slug, teacherCode.trim()).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", org.slug] });
      queryClient.invalidateQueries({ queryKey: ["classroom-hub"] });
      toast.success(`You teach at ${org.name} now`);
    },
    onError: (err) => toast.error(errorText(err, "Wrong teacher code")),
  });

  return (
    <div className="grid md:grid-cols-2 gap-px bg-[var(--line-strong)] mt-8">
      <form className="bg-ink-950 p-5" onSubmit={(e) => { e.preventDefault(); joinClass.mutate(); }}>
        <div className={SECTION_LABEL}>Student · class code from your teacher</div>
        <div className="flex gap-2">
          <input value={classCode} onChange={(e) => setClassCode(e.target.value.toUpperCase())} maxLength={8} placeholder="CLASS CODE" className={`${INPUT} font-mono tracking-[0.2em]`} />
          <button type="submit" disabled={classCode.trim().length < 8 || joinClass.isPending} className={ACTION}>Join</button>
        </div>
      </form>
      <form className="bg-ink-950 p-5" onSubmit={(e) => { e.preventDefault(); joinTeacher.mutate(); }}>
        <div className={SECTION_LABEL}>Teacher · code from the school admin</div>
        <div className="flex gap-2">
          <input value={teacherCode} onChange={(e) => setTeacherCode(e.target.value.toUpperCase())} maxLength={8} placeholder="TEACHER CODE" className={`${INPUT} font-mono tracking-[0.2em]`} />
          <button type="submit" disabled={teacherCode.trim().length < 8 || joinTeacher.isPending} className={ACTION}>Join</button>
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
    onError: (err) => toast.error(errorText(err, "Could not create the class")),
  });

  const visible = list.filter((c) => !c.archived);
  const archived = list.filter((c) => c.archived);
  const heading = org.role === "admin" ? "All classes" : "Your classes";

  return (
    <section>
      <div className={SECTION_LABEL}>{heading}</div>
      {visible.length === 0 ? (
        <p className="text-sm text-ink-500 py-2">{canCreate ? "No classes yet." : "You are not in any class here."}</p>
      ) : (
        <div className="divide-y divide-[var(--line-strong)]">
          {visible.map((c) => (
            <Link key={c.id} to={classPath(c)} className="grid grid-cols-[auto_1fr_auto] gap-4 items-center py-3 hover:bg-ink-800/40 px-2 -mx-2 transition-colors">
              <GraduationCap size={16} className="text-signal-sage/80" />
              <span className="text-ink-50">{c.name} <span className="text-ink-500 text-sm">· {levelLabel(c.level)}</span></span>
              <span className="font-mono text-[11px] text-ink-500 flex items-center gap-1.5">
                {org.role === "student" ? c.owner_name : <><Users size={12} /> {c.student_count}{org.role === "admin" && ` · ${c.owner_name}`}</>}
              </span>
            </Link>
          ))}
        </div>
      )}
      {archived.length > 0 && (
        <details className="mt-3">
          <summary className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 cursor-pointer">Archived ({archived.length})</summary>
          {archived.map((c) => (
            <Link key={c.id} to={classPath(c)} className="block py-2 text-ink-400 hover:text-ink-100">{c.name}</Link>
          ))}
        </details>
      )}
      {canCreate && (
        <form className="flex gap-2 mt-4" onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(); }}>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} placeholder="History 10B, spring" className={INPUT} />
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value === "" ? "" : Number(e.target.value))}
            aria-label="Year"
            className="bg-ink-950 border border-[var(--line-strong)] px-2 text-ink-100 focus:border-signal-amber outline-none"
          >
            <option value="">Year…</option>
            {LEVEL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button type="submit" disabled={!name.trim() || create.isPending} className={`${ACTION} flex items-center gap-1.5`}><Plus size={13} /> Class</button>
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
      toast.success("New teacher code issued; the old one no longer works");
    },
  });
  const remove = useMutation({
    mutationFn: (userId: number) => orgs.removeTeacher(org.slug, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["org-teachers", org.slug] }),
    onError: (err) => toast.error(errorText(err, "Could not remove")),
  });

  return (
    <section>
      <div className={`${SECTION_LABEL} flex justify-between`}>
        <span>Teachers</span>
        {org.teacher_seats ? <span className="tabular-nums">{org.teacher_seats_used} / {org.teacher_seats} seats</span> : null}
      </div>
      <div className="flex items-center gap-2 border border-[var(--line-strong)] px-3 py-2 mb-4">
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">teacher code</span>
        <span className="font-mono tracking-[0.2em] text-ink-50 flex-1">{org.teacher_code}</span>
        <button type="button" aria-label="Copy code" onClick={() => navigator.clipboard.writeText(org.teacher_code || "")} className="text-ink-400 hover:text-signal-amber"><Copy size={13} /></button>
        <button type="button" aria-label="New code" onClick={() => rotate.mutate()} className="text-ink-400 hover:text-signal-amber"><RefreshCw size={13} /></button>
      </div>
      <p className="text-xs text-ink-500 mb-3">Teachers open this page, enter the code, and create classes under the school plan.</p>
      <div className="divide-y divide-[var(--line-strong)]">
        {teachers.map((t) => (
          <div key={t.user_id} className="flex items-center gap-3 py-2">
            <span className="flex-1 truncate text-ink-100">{t.username}</span>
            <span className="font-mono text-[11px] text-ink-500">{t.role === "admin" ? "admin" : `${t.classes} classes`}</span>
            {t.user_id !== user?.id && t.role !== "admin" && (
              <button type="button" aria-label="Remove teacher" onClick={() => remove.mutate(t.user_id)} className="text-ink-600 hover:text-signal-blood"><UserMinus size={13} /></button>
            )}
          </div>
        ))}
      </div>
      {org.plan_active === false && (
        <p className="text-xs text-signal-blood mt-4">
          The Education plan on this school has lapsed: teachers cannot create classes and students cannot submit.{" "}
          <a href={`${MAIN_URL}/pricing`} className="underline">Renew</a>
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
      toast.success(`${org.name} has been deleted`);
      navigate("/");
    },
    onError: (err) => toast.error(errorText(err, "Could not delete the school")),
  });
  const ready = password.length > 0 && confirmSlug.trim() === org.slug && !destroy.isPending;

  return (
    <form
      className="mt-10 border border-signal-blood/40 p-4"
      onSubmit={(e) => { e.preventDefault(); if (ready) destroy.mutate(); }}
    >
      <div className={`${SECTION_LABEL} text-signal-blood`}>Delete school</div>
      <p className="text-xs text-ink-400 mb-2">
        This deletes {org.name}, all of its classes and all work handed in to them. It cannot be undone.
      </p>
      <p className="text-xs text-ink-500 mb-4">
        Deleted data can remain in database backups for up to 14 days, after which the backups expire.
      </p>
      <label className="block text-xs text-ink-500 mb-1" htmlFor="delete-school-slug">
        Type <span className="font-mono text-ink-100">{org.slug}</span> to confirm
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
      <label className="block text-xs text-ink-500 mb-1" htmlFor="delete-school-password">Your password</label>
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
          <Trash2 size={13} /> Delete
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
  if (!org) return <p className="text-ink-500">Loading…</p>;

  return (
    <div>
      <span className="label-mono">classroom.prooflayer.cloud/{org.slug}</span>
      <h1 className="font-display text-5xl text-ink-50 leading-tight mt-2">{org.name}</h1>

      {!isAuthenticated ? (
        <div className="mt-6 max-w-xl">
          <p className="text-ink-400">Sign in to see your classes at {org.name} or hand in work.</p>
          <div className="flex gap-3 mt-5">
            <Link to={`/login?next=/${org.slug}`} className={`${ACTION} py-2`}>Sign in</Link>
            <Link to={`/register?next=/${org.slug}`} className="border border-[var(--line-strong)] px-4 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-300 hover:text-ink-50">Create account</Link>
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
