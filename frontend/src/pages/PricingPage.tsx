import clsx from "clsx";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { initPaddle, openCheckout } from "../billing/paddle";
import { motion } from "motion/react";
import { ArrowLeft, Building2, Check, Gem, GraduationCap, Mail, School, ShieldCheck, Sparkles, X, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import { billing } from "../api/endpoints";
import { toast } from "../components/ui/Toast";
import { useAuthStore } from "../stores/authStore";
import type { BillingInterval, PlanInfo, PlanKey } from "../types";
import LangSwitch from "../components/LangSwitch";
import { currentLang, msg, t } from "../i18n";

const SALES_EMAIL = "sales@prooflayer.cloud";

type Audience = "personal" | "education";

const AUDIENCE_PLANS: Record<Audience, PlanKey[]> = {
  personal: ["free", "pro", "enterprise"],
  education: ["education", "university"],
};

const LOOK: Record<PlanKey, { Icon: typeof Zap; accent: string; ring: string }> = {
  free: { Icon: Zap, accent: "text-ink-300", ring: "border-[var(--line-strong)]" },
  pro: { Icon: Gem, accent: "text-signal-violet", ring: "border-iris/50" },
  education: { Icon: School, accent: "text-signal-sage", ring: "border-signal-sage/40" },
  university: { Icon: GraduationCap, accent: "text-signal-cyan", ring: "border-signal-cyan/40" },
  enterprise: { Icon: Building2, accent: "text-signal-amber", ring: "border-[var(--line-strong)]" },
};

const fmt = (n: number) => n.toLocaleString("en-US").replace(/,/g, " ");
const money = (n: number) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).replace(/,/g, " ");

function Price({ amount }: { amount: number }) {
  const cents = Math.round(amount * 100);
  const whole = Math.floor(cents / 100);
  const rest = cents % 100;
  return (
    <span className="font-display text-5xl text-ink-50 tabular-nums leading-none">
      <span className="text-2xl align-top mr-0.5 text-ink-300">$</span>
      {fmt(whole)}
      {rest > 0 && <span className="text-2xl align-top text-ink-300">.{String(rest).padStart(2, "0")}</span>}
    </span>
  );
}

const TABLE_ROWS: { label: string; value: (p: PlanInfo) => string | boolean }[] = [
  { label: msg("Checks / month"), value: (p) => fmt(p.uploads_per_month) },
  { label: msg("Every Tribunal member"), value: () => true },
  { label: msg("Public feed & community"), value: () => true },
  { label: msg("PDF reports"), value: (p) => p.pdf },
  { label: msg("Compare tool"), value: (p) => p.compare },
  { label: msg("API keys & webhooks"), value: (p) => (p.api ? t("{n}/min", { n: p.api_per_minute }) : false) },
  { label: msg("Classroom addresses"), value: (p) => (p.classroom ? String(p.schools) : false) },
  { label: msg("Teacher seats"), value: (p) => (p.teacher_seats ? String(p.teacher_seats) : false) },
  { label: msg("Priority support"), value: (p) => p.priority_support },
  { label: msg("Uptime SLA"), value: (p) => p.sla },
  { label: msg("On-premise option"), value: (p) => p.on_premise },
];

function Cell({ val }: { val: string | boolean }) {
  if (typeof val === "string") return <span className="text-xs text-ink-200 tabular-nums">{val}</span>;
  return val ? <Check size={14} strokeWidth={2.5} className="text-signal-sage mx-auto" /> : <X size={12} strokeWidth={2} className="text-ink-700 mx-auto" />;
}

function mailSales(plan: PlanInfo) {
  window.open(`mailto:${SALES_EMAIL}?subject=${encodeURIComponent(`ProofLayer ${plan.name} plan`)}`, "_blank");
}

function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: React.ReactNode }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] p-1">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={clsx("relative px-4 py-1.5 rounded-full text-sm transition-colors", active ? "text-ink-950" : "text-ink-400 hover:text-ink-100")}
          >
            {active && <motion.span layoutId={`seg-${label}`} className="absolute inset-0 rounded-full bg-ink-100" transition={{ type: "spring", stiffness: 500, damping: 35 }} />}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export default function PricingPage() {
  const [billingInterval, setBillingInterval] = useState<BillingInterval>("month");
  const [audience, setAudience] = useState<Audience>("education");
  const [checkoutPlan, setCheckoutPlan] = useState<PlanKey | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const { isAuthenticated, user } = useAuthStore();

  const { data: catalogData, isError } = useQuery({
    queryKey: ["plans"],
    queryFn: () => billing.plans().then((r) => r.data),
    staleTime: 5 * 60_000,
  });
  const catalog = catalogData?.plans;
  const paddleConfig = catalogData?.paddle ?? null;
  const queryClient = useQueryClient();

  useEffect(() => {
    if (paddleConfig && new URLSearchParams(window.location.search).has("_ptxn")) initPaddle(paddleConfig).catch(() => undefined);
  }, [paddleConfig]);
  const { data: sub } = useQuery({
    queryKey: ["subscription"],
    queryFn: () => billing.subscription().then((r) => r.data),
    enabled: isAuthenticated,
  });

  const handlePortal = async () => {
    setPortalLoading(true);
    try {
      const res = await billing.portal();
      window.location.href = res.data.url;
    } catch {
      toast.error(t("Failed to open billing portal"));
      setPortalLoading(false);
    }
  };

  const handleCheckout = async (plan: PlanInfo) => {
    if (!isAuthenticated) {
      window.location.href = "/register?next=/pricing";
      return;
    }
    setCheckoutPlan(plan.key);
    try {
      const res = await billing.checkout(plan.key, billingInterval);
      if (paddleConfig && res.data.transaction_id) {
        await openCheckout(paddleConfig, res.data.transaction_id, currentLang(), () => {
          toast.success(t("Payment received. Your plan updates in a moment."));
          setTimeout(() => queryClient.invalidateQueries({ queryKey: ["subscription"] }), 4000);
        });
        setCheckoutPlan(null);
      } else {
        window.location.href = res.data.url;
      }
    } catch (err) {
      const code = (err as { response?: { data?: { code?: string } } })?.response?.data?.code;
      setCheckoutPlan(null);
      if (code === "manage_in_portal") handlePortal();
      else if (code === "contact_sales") mailSales(plan);
      else toast.error(t("Failed to start checkout"));
    }
  };

  const plans = catalog ?? [];
  const shown = AUDIENCE_PLANS[audience].map((key) => plans.find((p) => p.key === key)).filter((p): p is PlanInfo => !!p);
  const paid = sub && sub.tier !== "free";
  const usedPct = sub ? Math.min(100, (sub.uploads_used / sub.uploads_limit) * 100) : 0;

  return (
    <div className="min-h-screen bg-ink-950">
      {!isAuthenticated ? (
        <header className="sticky top-0 z-30 backdrop-blur-xl bg-ink-950/30 border-b border-white/5">
          <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
            <Link to="/" className="font-display text-xl text-ink-50 leading-none">
              Proof<span className="italic text-iris">Layer</span>
            </Link>
            <div className="flex items-center gap-3">
              <LangSwitch />
              <Link to="/login" className="text-sm text-ink-400 hover:text-ink-100 transition px-3 py-2">{t("Sign in")}</Link>
              <Link to="/register" className="text-sm rounded-full bg-iris hover:bg-iris-light text-white px-4 py-2 transition">{t("Get Started")}</Link>
            </div>
          </div>
        </header>
      ) : (
        <div className="max-w-6xl mx-auto px-6 pt-6">
          <Link to="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-200 transition">
            <ArrowLeft size={14} strokeWidth={1.5} /> {t("Dashboard")}
          </Link>
        </div>
      )}

      <div className="max-w-6xl mx-auto px-6 py-14">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="text-center">
          <div className="inline-flex items-center gap-2 text-xs text-ink-400 rounded-full border border-white/10 px-3 py-1 mb-6">
            <Sparkles size={12} strokeWidth={1.5} className="text-iris" />
            {t("Simple, transparent pricing")}
          </div>
          <h1 className="font-display text-4xl md:text-6xl text-ink-50 leading-tight">
            {t("Verify more.")} <span className="italic text-iris">{t("Pay less.")}</span>
          </h1>
          <p className="text-ink-400 mt-4 max-w-xl mx-auto leading-relaxed">
            {t("Every plan runs the full Tribunal. You pay for volume, team tools and support, never for accuracy.")}
          </p>

          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Segmented
              label={t("Who it is for")}
              value={audience}
              onChange={setAudience}
              options={[
                { value: "education", label: t("Schools and universities") },
                { value: "personal", label: t("Individuals and teams") },
              ]}
            />
            <Segmented
              label={t("Billing interval")}
              value={billingInterval}
              onChange={setBillingInterval}
              options={[
                { value: "month", label: t("Monthly") },
                { value: "year", label: <>{t("Yearly")} <span className={billingInterval === "year" ? "text-signal-sage/90" : "text-signal-sage"}>−17%</span></> },
              ]}
            />
          </div>
        </motion.div>

        {sub && !user?.is_staff && (
          <div className="mt-10 rounded-lg border border-white/10 bg-white/[0.02] p-4 flex items-center gap-4">
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1.5 text-xs">
                <span className="text-ink-400">{t("{plan} plan · this month", { plan: t(plans.find((p) => p.key === sub.tier)?.name ?? sub.tier) })}</span>
                <span className="text-ink-300 tabular-nums">{sub.uploads_used} / {fmt(sub.uploads_limit)}</span>
              </div>
              <div className="h-1.5 bg-ink-800 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-700" style={{ width: `${usedPct}%`, background: usedPct > 85 ? "#ef4444" : usedPct > 60 ? "#f59e0b" : "#7c6af7" }} />
              </div>
            </div>
            {paid && (
              <button onClick={handlePortal} disabled={portalLoading} className="shrink-0 text-xs rounded-full border border-white/15 text-ink-300 hover:text-ink-50 px-3 py-1.5 transition disabled:opacity-40">
                {portalLoading ? "..." : t("Manage")}
              </button>
            )}
          </div>
        )}

        {user?.is_staff && (
          <div className="mt-10 rounded-lg border border-red-400/20 bg-red-400/[0.04] px-4 py-3 flex items-center gap-3 text-sm">
            <ShieldCheck size={16} strokeWidth={1.5} className="text-red-400 shrink-0" />
            <span className="text-ink-300">{t("Unrestricted access for staff: no quotas, review queue, verdict overrides, admin panel.")}</span>
          </div>
        )}

        {isError && (
          <p className="text-center text-sm text-ink-400 mt-10">
            {t("Pricing could not load. Write to")} <a className="underline" href={`mailto:${SALES_EMAIL}`}>{SALES_EMAIL}</a>.
          </p>
        )}

        <div className={clsx("grid gap-5 mt-10 mx-auto", shown.length === 2 ? "md:grid-cols-2 max-w-4xl" : "md:grid-cols-3")}>
          {shown.map((plan, i) => {
            const look = LOOK[plan.key];
            const Icon = look.Icon;
            const current = !user?.is_staff && sub?.tier === plan.key;
            const featured = plan.key === "pro" || plan.key === "education";
            const yearly = billingInterval === "year";
            const price = yearly && plan.yearly_usd != null ? plan.yearly_usd / 12 : plan.monthly_usd;
            const canPay = plan.checkout[billingInterval];
            const isFree = plan.key === "free";
            const loading = checkoutPlan === plan.key;
            return (
              <motion.div
                key={plan.key}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
                className={clsx("relative flex flex-col rounded-xl border bg-white/[0.02] p-7", featured ? look.ring : "border-white/10", featured && "beam-border shadow-[0_0_60px_-30px_rgba(124,106,247,0.6)]")}
              >
                {(current || featured) && (
                  <span className={clsx("absolute -top-3 left-7 text-[11px] rounded-full px-2.5 py-0.5 border bg-ink-950", current ? "text-signal-sage border-signal-sage/40" : "text-signal-violet border-iris/40")}>
                    {current ? t("Current plan") : t("Popular")}
                  </span>
                )}
                <div className="flex items-center gap-2.5">
                  <Icon size={18} strokeWidth={1.5} className={look.accent} />
                  <span className="text-lg text-ink-50">{t(plan.name)}</span>
                </div>
                <p className="text-sm text-ink-400 mt-2 min-h-[2.5rem]">{t(plan.audience)}</p>

                <div className="mt-6 flex items-baseline gap-2">
                  {price == null ? <span className="font-display text-5xl text-ink-50">{t("Custom")}</span> : <Price amount={price} />}
                  {price != null && <span className="text-sm text-ink-500">{isFree ? t("forever") : t("/ month")}</span>}
                </div>
                <div className="text-xs text-ink-500 h-4 mt-1.5">
                  {yearly && !isFree && plan.yearly_usd != null && plan.monthly_usd != null ? (
                    <>
                      <span className="line-through text-ink-600 mr-1.5">${money(plan.monthly_usd * 12)}</span>
                      {t("${n} billed once a year", { n: money(plan.yearly_usd) })}
                    </>
                  ) : ""}
                </div>

                <button
                  type="button"
                  onClick={() => {
                    if (isFree || current) return;
                    if (canPay) handleCheckout(plan);
                    else mailSales(plan);
                  }}
                  disabled={isFree || current || loading}
                  aria-label={t("{plan} plan", { plan: t(plan.name) })}
                  className={clsx(
                    "mt-6 w-full rounded-full py-2.5 text-sm transition-colors disabled:cursor-default",
                    featured ? "bg-iris hover:bg-iris-light text-white" : "border border-white/15 text-ink-100 hover:bg-white/[0.06]",
                    (isFree || current) && "opacity-50",
                  )}
                >
                  {isFree
                    ? t("Free forever")
                    : current
                    ? t("Current plan")
                    : loading
                    ? t("Redirecting...")
                    : canPay
                    ? isAuthenticated ? t("Subscribe") : t("Get {plan}", { plan: t(plan.name) })
                    : <span className="inline-flex items-center gap-1.5"><Mail size={14} strokeWidth={1.5} />{t("Talk to sales")}</span>}
                </button>

                <ul className="mt-7 space-y-3 border-t border-white/5 pt-6">
                  {plan.highlights.map((f) => (
                    <li key={f} className="flex items-start gap-2.5 text-sm text-ink-300">
                      <Check size={15} strokeWidth={2.2} className={clsx("shrink-0 mt-0.5", look.accent)} />
                      <span>{t(f)}</span>
                    </li>
                  ))}
                </ul>
              </motion.div>
            );
          })}
        </div>

        {plans.length > 0 && (
          <div className="mt-16">
            <h2 className="text-lg text-ink-50 mb-4">{t("Full feature comparison")}</h2>
            <div className="overflow-x-auto rounded-xl border border-white/10">
              <table className="w-full min-w-[680px] text-sm">
                <thead>
                  <tr className="border-b border-white/10 bg-white/[0.02]">
                    <th className="text-left px-5 py-3 font-normal text-ink-500">{t("Feature")}</th>
                    {plans.map((p) => (
                      <th key={p.key} className={clsx("px-3 py-3 font-normal text-center", LOOK[p.key].accent)}>{t(p.name)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {TABLE_ROWS.map((row) => (
                    <tr key={row.label} className="border-b border-white/[0.04] last:border-0">
                      <td className="px-5 py-3 text-ink-300">{t(row.label)}</td>
                      {plans.map((p) => (
                        <td key={p.key} className="px-3 py-3 text-center"><Cell val={row.value(p)} /></td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="mt-16 grid md:grid-cols-2 gap-4">
          {[
            { q: t("School or University?"), a: t("School covers one school address and 30 teachers. University covers up to 10 faculties, each with its own address, and 250 teachers. Students are always free and unlimited.") },
            { q: t("Who pays for student uploads?"), a: t("The school's plan. Students never need to upgrade, and their personal checks stay private from teachers.") },
            { q: t("Can I cancel anytime?"), a: t("Yes. Cancel in the billing portal and keep access until the period ends.") },
            { q: t("Need more volume or an invoice?"), a: t("Enterprise is priced for your volume, with invoicing, purchase orders and on-premise. Write to {email}.", { email: SALES_EMAIL }) },
          ].map(({ q, a }) => (
            <div key={q} className="rounded-xl border border-white/10 p-6">
              <div className="text-ink-100">{q}</div>
              <div className="text-sm text-ink-400 mt-2 leading-relaxed">{a}</div>
            </div>
          ))}
        </div>

        {!isAuthenticated && (
          <div className="mt-14 flex flex-wrap items-center justify-center gap-x-8 gap-y-2 text-xs text-ink-600">
            <Link to="/terms" className="hover:text-ink-400 transition">{t("Terms")}</Link>
            <Link to="/privacy" className="hover:text-ink-400 transition">{t("Privacy")}</Link>
            <Link to="/refund" className="hover:text-ink-400 transition">{t("Refund Policy")}</Link>
            <a href={`mailto:${SALES_EMAIL}`} className="hover:text-ink-400 transition">{SALES_EMAIL}</a>
          </div>
        )}
      </div>
    </div>
  );
}
