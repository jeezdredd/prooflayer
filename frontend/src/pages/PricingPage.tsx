import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
  Check, X, Zap, Building2, GraduationCap, Gem, School,
  ArrowLeft, Sparkles, Mail, ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { billing } from "../api/endpoints";
import { toast } from "../components/ui/Toast";
import { useAuthStore } from "../stores/authStore";
import type { BillingInterval, PlanInfo, PlanKey } from "../types";

const SALES_EMAIL = "sales@prooflayer.cloud";

const LOOK: Record<PlanKey, { Icon: typeof Zap; accent: string; icon?: string; check: string; button: string; eyebrow?: string }> = {
  free: { Icon: Zap, accent: "text-ink-400", check: "text-signal-sage", button: "border border-ink-800 text-ink-600" },
  pro: { Icon: Gem, accent: "text-iris", icon: "text-violet-400", check: "text-violet-400", button: "bg-iris hover:bg-iris-light text-white" },
  education: { Icon: School, accent: "text-signal-sage", check: "text-signal-sage", button: "border border-signal-sage/40 text-signal-sage hover:bg-signal-sage/10", eyebrow: "Education" },
  university: { Icon: GraduationCap, accent: "text-signal-cyan", check: "text-signal-cyan", button: "border border-signal-cyan/40 text-signal-cyan hover:bg-signal-cyan/10", eyebrow: "Education" },
  enterprise: { Icon: Building2, accent: "text-signal-amber", check: "text-signal-amber", button: "border border-signal-amber/40 text-signal-amber hover:bg-signal-amber/10" },
};

const fmt = (n: number) => n.toLocaleString("en-US").replace(/,/g, " ");

const TABLE_ROWS: { label: string; value: (p: PlanInfo) => string | boolean }[] = [
  { label: "Checks / month", value: (p) => fmt(p.uploads_per_month) },
  { label: "Every Tribunal member", value: () => true },
  { label: "Public feed & community", value: () => true },
  { label: "PDF reports", value: (p) => p.pdf },
  { label: "Compare tool", value: (p) => p.compare },
  { label: "Widget embed", value: (p) => p.embed },
  { label: "API keys & webhooks", value: (p) => (p.api ? `${p.api_per_minute}/min` : false) },
  { label: "Classroom addresses", value: (p) => (p.classroom ? String(p.schools) : false) },
  { label: "Teacher seats", value: (p) => (p.teacher_seats ? String(p.teacher_seats) : false) },
  { label: "Priority support", value: (p) => p.priority_support },
  { label: "Uptime SLA", value: (p) => p.sla },
  { label: "On-premise option", value: (p) => p.on_premise },
];

function Cell({ val }: { val: string | boolean }) {
  if (typeof val === "string") {
    return <span className="font-mono text-[11px] text-ink-200 tabular-nums">{val}</span>;
  }
  return val
    ? <Check size={14} strokeWidth={2.5} className="text-signal-sage mx-auto" />
    : <X size={12} strokeWidth={2} className="text-ink-700 mx-auto" />;
}

function mailSales(plan: PlanInfo) {
  window.open(`mailto:${SALES_EMAIL}?subject=${encodeURIComponent(`ProofLayer ${plan.name} plan`)}`, "_blank");
}

export default function PricingPage() {
  const [billingInterval, setBillingInterval] = useState<BillingInterval>("month");
  const [checkoutPlan, setCheckoutPlan] = useState<PlanKey | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const { isAuthenticated, user } = useAuthStore();

  const { data: catalog, isError } = useQuery({
    queryKey: ["plans"],
    queryFn: () => billing.plans().then((r) => r.data.plans),
    staleTime: 5 * 60_000,
  });
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
      toast.error("Failed to open billing portal");
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
      window.location.href = res.data.url;
    } catch (err) {
      const code = (err as { response?: { data?: { code?: string } } })?.response?.data?.code;
      setCheckoutPlan(null);
      if (code === "manage_in_portal") handlePortal();
      else if (code === "contact_sales") mailSales(plan);
      else toast.error("Failed to start checkout");
    }
  };

  const paid = sub && sub.tier !== "free";
  const usedPct = sub ? Math.min(100, (sub.uploads_used / sub.uploads_limit) * 100) : 0;
  const plans = catalog ?? [];

  return (
    <div className="min-h-screen bg-ink-950">
      {!isAuthenticated ? (
        <header className="sticky top-0 z-30 backdrop-blur-xl bg-ink-950/90 border-b border-white/5">
          <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
            <Link to="/" className="font-display text-xl text-ink-50 leading-none">
              Proof<span className="italic text-iris">Layer</span>
            </Link>
            <div className="flex items-center gap-3">
              <Link to="/login" className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-400 hover:text-ink-100 transition px-3 py-2">
                Login
              </Link>
              <Link to="/register" className="font-mono text-[11px] uppercase tracking-[0.14em] bg-iris hover:bg-iris-light text-white px-4 py-2 transition">
                Get Started →
              </Link>
            </div>
          </div>
        </header>
      ) : (
        <div className="max-w-6xl mx-auto px-6 pt-6">
          <Link to="/dashboard" className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500 hover:text-ink-200 transition">
            <ArrowLeft size={12} strokeWidth={1.5} /> Dashboard
          </Link>
        </div>
      )}

      <div className="max-w-6xl mx-auto px-6 py-16">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-10">
          <div className="inline-flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.22em] text-ink-400 border border-white/12 px-3 py-1.5 mb-6">
            <Sparkles size={10} strokeWidth={1.5} className="text-iris" />
            Simple, transparent pricing
          </div>
          <h1 className="font-display text-4xl md:text-5xl text-ink-50 mb-4 leading-tight">
            Verify more.<br />
            <span className="italic text-iris">Pay less.</span>
          </h1>
          <p className="text-ink-400 text-sm max-w-lg mx-auto leading-relaxed">
            Every plan runs the full Tribunal. You pay for volume, team tools and support, never for accuracy.
          </p>
        </motion.div>

        <div className="flex justify-center mb-10">
          <div role="radiogroup" aria-label="Billing interval" className="inline-flex border border-white/10 p-1 font-mono text-[11px] uppercase tracking-[0.14em]">
            {(["month", "year"] as BillingInterval[]).map((i) => (
              <button
                key={i}
                type="button"
                role="radio"
                aria-checked={billingInterval === i}
                onClick={() => setBillingInterval(i)}
                className={`px-4 py-2 transition-colors ${billingInterval === i ? "bg-white/10 text-ink-50" : "text-ink-500 hover:text-ink-200"}`}
              >
                {i === "month" ? "Monthly" : <>Yearly <span className="text-signal-sage normal-case tracking-normal">· 2 months free</span></>}
              </button>
            ))}
          </div>
        </div>

        {sub && !user?.is_staff && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-10 p-4 border border-white/6 bg-white/[0.02] flex items-center gap-4">
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
                  {plans.find((p) => p.key === sub.tier)?.name ?? sub.tier} plan · this month
                </span>
                <span className="font-mono text-[10px] text-ink-400 tabular-nums">
                  {sub.uploads_used} / {fmt(sub.uploads_limit)}
                </span>
              </div>
              <div className="h-1 bg-ink-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${usedPct}%`, background: usedPct > 85 ? "#ef4444" : usedPct > 60 ? "#f59e0b" : "#7c6af7" }}
                />
              </div>
            </div>
            {paid && (
              <button
                onClick={handlePortal}
                disabled={portalLoading}
                className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] border border-ink-700 text-ink-400 hover:text-ink-200 hover:border-ink-500 px-3 py-1.5 transition disabled:opacity-40"
              >
                {portalLoading ? "..." : "Manage"}
              </button>
            )}
          </motion.div>
        )}

        {isError && (
          <p className="text-center text-sm text-ink-400 mb-10">
            Pricing could not load. Write to <a className="underline" href={`mailto:${SALES_EMAIL}`}>{SALES_EMAIL}</a>.
          </p>
        )}

        <div className={`grid grid-cols-1 md:grid-cols-2 gap-px bg-white/5 border border-white/5 mb-1 ${user?.is_staff ? "lg:grid-cols-3 xl:grid-cols-6" : "lg:grid-cols-5"}`}>
          {plans.map((plan, i) => {
            const look = LOOK[plan.key];
            const Icon = look.Icon;
            const current = !user?.is_staff && sub?.tier === plan.key;
            const featured = plan.key === "pro";
            const price = billingInterval === "year" ? plan.yearly_usd : plan.monthly_usd;
            const canPay = plan.checkout[billingInterval];
            const isFree = plan.key === "free";
            const loading = checkoutPlan === plan.key;
            return (
              <motion.div
                key={plan.key}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
                className={`relative flex flex-col p-6 bg-ink-950 ${featured ? "ring-1 ring-iris/40 z-10" : ""}`}
              >
                {featured && <div className="absolute -top-px left-6 right-6 h-px bg-gradient-to-r from-transparent via-iris to-transparent" />}
                {(current || featured) && (
                  <div className="absolute top-4 right-4">
                    <span className="font-mono text-[8px] uppercase tracking-[0.18em] border px-2 py-0.5 text-iris bg-iris/10 border-iris/20">
                      {current ? "Active" : "Popular"}
                    </span>
                  </div>
                )}

                <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-600 h-3 mb-2">{look.eyebrow ?? ""}</div>
                <div className="flex items-center gap-2 mb-5 pr-14">
                  <Icon size={15} strokeWidth={1.5} className={look.icon ?? look.accent} />
                  <span className={`font-mono text-[11px] uppercase tracking-[0.16em] truncate ${look.accent}`}>{plan.name}</span>
                </div>

                <div className="mb-5">
                  <div className="flex items-baseline gap-1.5">
                    <span className={`font-display text-3xl ${featured ? "text-ink-50" : "text-ink-200"}`}>{price == null ? "Custom" : `$${fmt(price)}`}</span>
                    <span className="font-mono text-[11px] text-ink-600">{isFree ? "forever" : price == null ? "pricing" : billingInterval === "year" ? "/ year" : "/ month"}</span>
                  </div>
                  <div className="font-mono text-[10px] text-ink-600 h-4 mt-1">
                    {billingInterval === "year" && !isFree && plan.yearly_usd != null ? `≈ $${fmt(Math.round(plan.yearly_usd / 12))} a month` : ""}
                  </div>
                  <p className="font-mono text-[11px] text-ink-500 mt-2 leading-relaxed">{plan.audience}</p>
                </div>

                <ul className="flex-1 space-y-2.5 mb-7">
                  {plan.highlights.map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <Check size={12} strokeWidth={2.5} className={`shrink-0 mt-0.5 ${look.check}`} />
                      <span className="font-mono text-[11px] text-ink-300 leading-relaxed">{f}</span>
                    </li>
                  ))}
                </ul>

                <button
                  type="button"
                  onClick={() => {
                    if (isFree || current) return;
                    if (canPay) handleCheckout(plan);
                    else mailSales(plan);
                  }}
                  disabled={isFree || current || loading}
                  aria-label={`${plan.name} plan`}
                  className={`w-full py-3 font-mono text-[11px] uppercase tracking-[0.14em] transition-all ${look.button} disabled:opacity-40 disabled:cursor-default`}
                >
                  {isFree
                    ? "Free forever"
                    : current
                    ? "Current plan"
                    : loading
                    ? "Redirecting..."
                    : canPay
                    ? isAuthenticated ? "Subscribe →" : `Get ${plan.name} →`
                    : <span className="flex items-center justify-center gap-1.5"><Mail size={11} strokeWidth={1.5} />Talk to sales</span>}
                </button>
              </motion.div>
            );
          })}
          {user?.is_staff && plans.length > 0 && (
            <div className="relative flex flex-col p-6 bg-ink-950 ring-1 ring-red-400/20">
              <div className="h-3 mb-2" />
              <div className="flex items-center gap-2 mb-5">
                <ShieldCheck size={15} strokeWidth={1.5} className="text-red-400" />
                <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-red-400">Internal</span>
              </div>
              <div className="font-display text-3xl text-ink-200 mb-5">∞</div>
              <p className="font-mono text-[11px] text-ink-500 leading-relaxed flex-1">
                Unrestricted access for operators: no quotas, review queue, verdict overrides, admin panel.
              </p>
              <div className="w-full py-3 mt-7 text-center font-mono text-[11px] uppercase tracking-[0.14em] border border-red-400/30 text-red-400/60">Active</div>
            </div>
          )}
        </div>

        {plans.length > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mt-12 border border-white/5">
            <div className="px-6 py-4 border-b border-white/5 bg-white/[0.015]">
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-500">Full feature comparison</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px]">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="text-left px-6 py-3 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-600 font-normal w-1/4">Feature</th>
                    {plans.map((p) => (
                      <th key={p.key} className={`px-3 py-3 font-mono text-[10px] uppercase tracking-[0.14em] font-normal text-center ${LOOK[p.key].accent}`}>{p.name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {TABLE_ROWS.map((row, ri) => (
                    <tr key={row.label} className={`border-b border-white/[0.03] ${ri % 2 ? "bg-white/[0.01]" : ""}`}>
                      <td className="px-6 py-3 font-mono text-[11px] text-ink-400">{row.label}</td>
                      {plans.map((p) => (
                        <td key={p.key} className="px-3 py-3 text-center"><Cell val={row.value(p)} /></td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.div>
        )}

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }} className="mt-12 grid md:grid-cols-2 lg:grid-cols-4 gap-px bg-white/5 border border-white/5">
          {[
            { q: "School or University?", a: "School covers one school address and 30 teachers. University covers up to 10 faculties, each with its own address, and 250 teachers. Students are always free and unlimited." },
            { q: "Who pays for student uploads?", a: "The school's plan. Students never need to upgrade, and their personal checks stay private from teachers." },
            { q: "Can I cancel anytime?", a: "Yes. Cancel in the billing portal and keep access until the period ends." },
            { q: "Need more volume or an invoice?", a: `Enterprise is priced for your volume, with invoicing, purchase orders and on-premise. Write to ${SALES_EMAIL}.` },
          ].map(({ q, a }) => (
            <div key={q} className="p-6 bg-ink-950">
              <div className="font-mono text-[11px] text-ink-200 mb-2">{q}</div>
              <div className="font-mono text-[11px] text-ink-500 leading-relaxed">{a}</div>
            </div>
          ))}
        </motion.div>

        {!isAuthenticated && (
          <div className="mt-14 flex flex-wrap items-center justify-center gap-x-8 gap-y-2 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-700">
            <Link to="/terms" className="hover:text-ink-400 transition">Terms</Link>
            <Link to="/privacy" className="hover:text-ink-400 transition">Privacy</Link>
            <Link to="/refund" className="hover:text-ink-400 transition">Refund Policy</Link>
            <a href={`mailto:${SALES_EMAIL}`} className="hover:text-ink-400 transition">{SALES_EMAIL}</a>
          </div>
        )}
      </div>
    </div>
  );
}
