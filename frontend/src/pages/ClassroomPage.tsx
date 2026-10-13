import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GraduationCap, Plus, LogIn, Users } from "lucide-react";
import { classrooms } from "../api/endpoints";
import type { Classroom } from "../types";
import { useSubscriptionInfo } from "../components/SubscriptionGate";
import { useAuthStore } from "../stores/authStore";
import { toast } from "../components/ui/Toast";

function errorText(err: unknown, fallback: string) {
  const data = (err as { response?: { data?: { detail?: string } } })?.response?.data;
  return data?.detail || fallback;
}

function ClassList({ title, items }: { title: string; items: Classroom[] }) {
  if (items.length === 0) return null;
  return (
    <section className="mb-8">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500 mb-2">{title}</div>
      <div className="divide-y divide-[var(--line-strong)]">
        {items.map((c) => (
          <Link key={c.id} to={`/classroom/${c.id}`}
            className="grid grid-cols-[auto_1fr_auto] gap-4 items-center py-3 hover:bg-ink-800/40 px-2 -mx-2 transition-colors">
            <GraduationCap size={16} className="text-signal-sage/80" />
            <span className={`text-ink-50 ${c.archived ? "opacity-50" : ""}`}>{c.name}{c.archived ? " · archived" : ""}</span>
            <span className="font-mono text-[11px] text-ink-500 flex items-center gap-1.5">
              {c.role === "teacher" ? <><Users size={12} /> {c.student_count}</> : c.owner_name}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default function ClassroomPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { data: sub } = useSubscriptionInfo();
  const canTeach = Boolean(sub?.can_classroom || user?.is_staff);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");

  const { data: list = [], isLoading } = useQuery({
    queryKey: ["classrooms"],
    queryFn: () => classrooms.list().then((r) => r.data),
  });

  const create = useMutation({
    mutationFn: () => classrooms.create(name.trim()).then((r) => r.data),
    onSuccess: (c) => {
      queryClient.invalidateQueries({ queryKey: ["classrooms"] });
      navigate(`/classroom/${c.id}`);
    },
    onError: (err) => toast.error(errorText(err, "Could not create classroom")),
  });

  const join = useMutation({
    mutationFn: () => classrooms.join(code.trim()).then((r) => r.data),
    onSuccess: (c) => {
      queryClient.invalidateQueries({ queryKey: ["classrooms"] });
      toast.success(`Joined ${c.name}`);
      navigate(`/classroom/${c.id}`);
    },
    onError: (err) => toast.error(errorText(err, "Could not join")),
  });

  return (
    <div>
      <div className="mb-8">
        <span className="label-mono">Education</span>
        <h1 className="font-display text-4xl text-white mt-2">Classroom</h1>
        <p className="text-sm text-ink-400 mt-2 max-w-2xl">
          Students submit their work to a class; the teacher sees every class submission with its Tribunal verdict.
          Personal uploads stay private.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-px bg-[var(--line-strong)] mb-10">
        <form
          className="bg-[var(--bg)] p-5"
          onSubmit={(e) => {
            e.preventDefault();
            if (code.trim()) join.mutate();
          }}
        >
          <div className="flex items-center gap-2 text-ink-50 font-display text-xl mb-3"><LogIn size={18} className="text-signal-amber/80" /> Join a class</div>
          <div className="flex gap-2">
            <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="CODE1234" maxLength={8}
              className="flex-1 bg-transparent border border-[var(--line-strong)] px-3 py-2 font-mono tracking-[0.2em] text-ink-50 focus:border-signal-amber outline-none" />
            <button type="submit" disabled={code.trim().length < 8 || join.isPending}
              className="border border-signal-amber/60 text-signal-amber px-4 font-mono text-[11px] uppercase tracking-[0.14em] hover:bg-signal-amber/10 disabled:opacity-40">Join</button>
          </div>
        </form>

        <form
          className="bg-[var(--bg)] p-5"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate();
          }}
        >
          <div className="flex items-center gap-2 text-ink-50 font-display text-xl mb-3"><Plus size={18} className="text-signal-amber/80" /> Create a class</div>
          {canTeach ? (
            <div className="flex gap-2">
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Year 10 · Media literacy" maxLength={120}
                className="flex-1 bg-transparent border border-[var(--line-strong)] px-3 py-2 text-ink-50 focus:border-signal-amber outline-none" />
              <button type="submit" disabled={!name.trim() || create.isPending}
                className="border border-signal-amber/60 text-signal-amber px-4 font-mono text-[11px] uppercase tracking-[0.14em] hover:bg-signal-amber/10 disabled:opacity-40">Create</button>
            </div>
          ) : (
            <p className="text-sm text-ink-400">
              Teaching needs the Education plan. <Link to="/pricing" className="underline hover:text-ink-100">See plans</Link>
            </p>
          )}
        </form>
      </div>

      {isLoading ? (
        <p className="text-ink-500">Loading…</p>
      ) : (
        <>
          <ClassList title="Teaching" items={list.filter((c) => c.role === "teacher")} />
          <ClassList title="Enrolled" items={list.filter((c) => c.role === "student")} />
        </>
      )}
    </div>
  );
}
