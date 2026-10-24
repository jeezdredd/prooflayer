import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, GraduationCap, LogIn, Plus, Users } from "lucide-react";
import { classrooms, orgs } from "../api/endpoints";
import type { Classroom } from "../types";
import { useAuthStore } from "../stores/authStore";
import { toast } from "../components/ui/Toast";
import { classPath, errorText, INPUT, ACTION, SECTION_LABEL, MAIN_URL } from "./shared";
import { AttentionLine, NameField } from "./ClassBits";
import { t } from "../i18n";

function ClassRow({ c }: { c: Classroom }) {
  return (
    <Link to={classPath(c)} className="grid grid-cols-[auto_1fr_auto] gap-4 items-center py-3 hover:bg-ink-800/40 px-2 -mx-2 transition-colors">
      <GraduationCap size={16} className="text-signal-sage/80" />
      <span className="text-ink-50 min-w-0">
        {c.name}
        {c.organization_name && <span className="text-ink-500"> · {c.organization_name}</span>}
        {c.role === "teacher" && <AttentionLine attention={c.attention} />}
      </span>
      <span className="font-mono text-[11px] text-ink-500 flex items-center gap-1.5">
        {c.role === "teacher" ? <><Users size={12} /> {c.student_count}</> : t("Teacher: {name}", { name: c.owner_name })}
      </span>
    </Link>
  );
}

export default function HubPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const studentOnly = !!user?.student_only;
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [slug, setSlug] = useState("");
  const { data: hub, isLoading } = useQuery({ queryKey: ["classroom-hub"], queryFn: () => orgs.hub().then((r) => r.data) });
  const needsName = !!hub && !hub.my_name;

  const join = useMutation({
    mutationFn: () => classrooms.join(code.trim(), needsName ? name.trim() : undefined).then((r) => r.data),
    onSuccess: (c) => {
      queryClient.invalidateQueries({ queryKey: ["classroom-hub"] });
      toast.success(t("Joined {name}", { name: c.name }));
      navigate(classPath(c));
    },
    onError: (err) => toast.error(errorText(err, t("Could not join"))),
  });

  const createOrg = useMutation({
    mutationFn: () => orgs.create(orgName.trim(), slug.trim(), needsName ? ownerName.trim() : undefined).then((r) => r.data),
    onSuccess: (o) => {
      queryClient.invalidateQueries({ queryKey: ["classroom-hub"] });
      navigate(`/${o.slug}`);
    },
    onError: (err) => toast.error(errorText(err, t("Could not create"))),
  });

  if (isLoading || !hub) return <p className="text-ink-500">{t("Loading…")}</p>;

  const ready = code.trim().length === 8 && (!needsName || name.trim().length > 1);

  return (
    <div>
      <h1 className="font-display text-5xl text-ink-50 leading-tight">{t("Your classroom")}</h1>
      <p className="text-ink-400 mt-3 max-w-2xl">
        {studentOnly
          ? t("Hand in work to your class here. Your teacher sees only the work you hand in to the class.")
          : t("Students hand in work to a class; teachers see each piece with its Tribunal verdict. Personal checks on the main site stay private.")}
      </p>

      <form
        className="mt-8 case-card p-5 max-w-xl"
        onSubmit={(e) => {
          e.preventDefault();
          if (ready) join.mutate();
        }}
      >
        <div className="flex items-center gap-2 text-ink-50 font-display text-xl mb-3"><LogIn size={18} className="text-signal-amber/80" /> {t("Join a class")}</div>
        {needsName && <NameField value={name} onChange={setName} />}
        <div className="flex gap-2">
          <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder={t("CLASS CODE")} maxLength={8} className={`${INPUT} font-mono tracking-[0.2em]`} />
          <button type="submit" disabled={!ready || join.isPending} className={ACTION}>{t("Join")}</button>
        </div>
      </form>

      {hub.organizations.length > 0 && (
        <section className="mt-10">
          <div className={SECTION_LABEL}>{t("Schools")}</div>
          <div className="divide-y divide-[var(--line-strong)]">
            {hub.organizations.map((o) => (
              <Link key={o.slug} to={`/${o.slug}`} className="grid grid-cols-[auto_1fr_auto] gap-4 items-center py-3 hover:bg-ink-800/40 px-2 -mx-2 transition-colors">
                <Building2 size={16} className="text-signal-amber/80" />
                <span className="text-ink-50 min-w-0">
                  {o.name}
                  <AttentionLine attention={o.attention} />
                </span>
                <span className="font-mono text-[11px] text-ink-500">{t(o.role ?? "")} · /{o.slug}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {hub.enrolled.length > 0 && (
        <section className="mt-10">
          <div className={SECTION_LABEL}>{t("Classes you attend")}</div>
          <div className="divide-y divide-[var(--line-strong)]">{hub.enrolled.map((c) => <ClassRow key={c.id} c={c} />)}</div>
        </section>
      )}

      {hub.personal_classes.length > 0 && (
        <section className="mt-10">
          <div className={SECTION_LABEL}>{t("Classes without a school")}</div>
          <div className="divide-y divide-[var(--line-strong)]">{hub.personal_classes.map((c) => <ClassRow key={c.id} c={c} />)}</div>
        </section>
      )}

      {!studentOnly && (
        <section className="mt-12 border-t border-[var(--line-strong)] pt-8 max-w-xl">
          <div className="flex items-center gap-2 text-ink-50 font-display text-xl mb-2"><Plus size={18} className="text-signal-amber/80" /> {t("Set up your school")}</div>
          {hub.can_create_organization ? (
            <form
              className="space-y-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (orgName.trim() && slug.trim() && (!needsName || ownerName.trim().length > 1)) createOrg.mutate();
              }}
            >
              {needsName && <NameField value={ownerName} onChange={setOwnerName} teacher />}
              <input value={orgName} onChange={(e) => setOrgName(e.target.value)} placeholder={t("Lyceum 239")} maxLength={120} className={`${INPUT} w-full`} />
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-xs text-ink-500">classroom.prooflayer.cloud/</span>
                <input
                  value={slug}
                  onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                  placeholder="lyceum-239"
                  maxLength={40}
                  className={`${INPUT} font-mono`}
                />
                <button type="submit" disabled={!orgName.trim() || slug.length < 3 || (needsName && ownerName.trim().length < 2) || createOrg.isPending} className={`${ACTION} py-2`}>{t("Create")}</button>
              </div>
              <p className="text-xs text-ink-500">{t("Teachers you invite work under the school's Education plan; they do not need their own.")}</p>
            </form>
          ) : (
            <p className="text-sm text-ink-400">
              {t("A school address needs the School or University plan. Teachers invited to an existing school can skip this.")}{" "}
              <a href={`${MAIN_URL}/pricing`} className="underline hover:text-ink-100">{t("See plans")}</a>
            </p>
          )}
        </section>
      )}
    </div>
  );
}
