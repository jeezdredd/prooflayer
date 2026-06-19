import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
  Check, X, Zap, Building2, GraduationCap, Gem,
  ArrowLeft, Sparkles, Mail, ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { billing } from "../api/endpoints";
import { toast } from "../components/ui/Toast";
import { useAuthStore } from "../stores/authStore";

const FEATURES_GRID = [
  { label: "Submissions / month", free: "50", pro: "500", edu: "2 000", ent: "Unlimited" },
  { label: "All detection analyzers",  free: true,  pro: true,  edu: true,  ent: true  },
  { label: "Vision LLM analysis",      free: true,  pro: true,  edu: true,  ent: true  },
  { label: "PDF reports",              free: true,  pro: true,  edu: true,  ent: true  },
  { label: "Public feed & community",  free: true,  pro: true,  edu: true,  ent: true  },
  { label: "Compare tool",             free: false, pro: true,  edu: true,  ent: true  },
  { label: "Widget embed",             free: false, pro: true,  edu: true,  ent: true  },
  { label: "API access",               free: false, pro: true,  edu: true,  ent: true  },
  { label: "Priority support",         free: false, pro: false, edu: true,  ent: true  },
  { label: "SLA guarantee",            free: false, pro: false, edu: false, ent: true  },
  { label: "On-premise option",        free: false, pro: false, edu: false, ent: true  },
];

function Cell({ val }: { val: string | boolean }) {
  if (typeof val === "string") {
    return <span className="font-mono text-[11px] text-ink-200 tabular-nums">{val}</span>;
  }
  return val
    ? <Check size={14} strokeWidth={2.5} className="text-signal-sage mx-auto" />
    : <X size={12} strokeWidth={2} className="text-ink-700 mx-auto" />;
}

export default function PricingPage() {
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);
  const { isAuthenticated, user } = useAuthStore();

  const { data: sub } = useQuery({
    queryKey: ["subscription"],
    queryFn: () => billing.subscription().then((r) => r.data),
    enabled: isAuthenticated,
  });

  const handleCheckout = async () => {
    if (!isAuthenticated) { window.location.href = "/register"; return; }
    setCheckoutLoading(true);
    try {
      const res = await billing.checkout();
      window.location.href = res.data.url;
    } catch {
      toast.error("Failed to start checkout");
      setCheckoutLoading(false);
    }
  };

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

  const isCurrent = (key: string) => {
    if (user?.is_staff) return key === "internal";
    return sub?.tier === key;
  };
  const usedPct = sub ? Math.min(100, (sub.uploads_used / sub.uploads_limit) * 100) : 0;

  return (
    <div className="min-h-screen bg-ink-950">

      {/* ── Public nav ── */}
      {!isAuthenticated ? (
        <header className="sticky top-0 z-30 backdrop-blur-xl bg-ink-950/90 border-b border-white/5">
          <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
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
        <div className="max-w-5xl mx-auto px-6 pt-6">
          <Link to="/dashboard" className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500 hover:text-ink-200 transition">
            <ArrowLeft size={12} strokeWidth={1.5} /> Dashboard
          </Link>
        </div>
      )}

      <div className="max-w-5xl mx-auto px-6 py-16">

        {/* ── Hero ── */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-14"
        >
          <div className="inline-flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.22em] text-ink-400 border border-white/12 px-3 py-1.5 mb-6">
            <Sparkles size={10} strokeWidth={1.5} className="text-iris" />
            Simple, transparent pricing
          </div>
          <h1 className="font-display text-4xl md:text-5xl text-ink-50 mb-4 leading-tight">
            Verify more.<br />
            <span className="italic text-iris">Pay less.</span>
          </h1>
          <p className="text-ink-400 text-sm max-w-md mx-auto leading-relaxed">
            All plans include every detector. Upgrade for higher limits and team tools.
          </p>
        </motion.div>

        {/* ── Usage bar (logged in, non-staff) ── */}
        {sub && !user?.is_staff && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mb-10 p-4 border border-white/6 bg-white/[0.02] flex items-center gap-4"
          >
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 capitalize">
                  {sub.tier} plan · this month
                </span>
                <span className="font-mono text-[10px] text-ink-400 tabular-nums">
                  {sub.uploads_used} / {sub.uploads_limit}
                </span>
              </div>
              <div className="h-1 bg-ink-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${usedPct}%`,
                    background: usedPct > 85 ? "#ef4444" : usedPct > 60 ? "#f59e0b" : "#7c6af7",
                  }}
                />
              </div>
            </div>
            {sub.tier === "pro" && (
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

        {/* ── Tier cards ── */}
        <div className={`grid grid-cols-1 md:grid-cols-2 gap-px bg-white/5 border border-white/5 mb-1 ${user?.is_staff ? "lg:grid-cols-5" : "lg:grid-cols-4"}`}>
          {/* FREE */}
          {[
            {
              key: "free", label: "Free", Icon: Zap,
              price: "$0", period: "forever",
              desc: "Get started with content verification.",
              accentClass: "text-ink-400", borderClass: "",
              features: ["50 submissions / month", "All analyzers", "Community feed", "PDF reports"],
            },
            {
              key: "pro", label: "Pro", Icon: Gem,
              price: "$12", period: "/ month",
              desc: "For journalists, researchers, power users.",
              accentClass: "text-iris", iconClass: "text-violet-400", borderClass: "",
              features: ["500 submissions / month", "Everything in Free", "Compare tool", "Widget embed", "API access"],
              featured: true,
            },
            {
              key: "education", label: "Education", Icon: GraduationCap,
              price: "Contact", period: "sales",
              desc: "Universities, schools, non-profits.",
              accentClass: "text-signal-sage", borderClass: "",
              features: ["2 000 submissions / month", "Everything in Pro", "Classroom dashboard", "Priority support"],
            },
            {
              key: "enterprise", label: "Enterprise", Icon: Building2,
              price: "Contact", period: "sales",
              desc: "Newsrooms, media companies, agencies.",
              accentClass: "text-signal-amber", borderClass: "",
              features: ["Unlimited submissions", "Everything in Pro", "On-premise option", "SLA", "Dedicated support"],
            },
            ...(user?.is_staff ? [{
              key: "internal", label: "Internal", Icon: ShieldCheck,
              price: "∞", period: "always",
              desc: "Grants unrestricted, full access to the ProofLayer system. Reserved for internal operators and system administrators.",
              accentClass: "text-red-400", iconClass: "text-red-400", borderClass: "",
              internal: true,
              features: ["Unlimited submissions", "All Pro features", "No rate limits", "Admin panel access", "Review queue", "Verdict overrides"],
            }] : []),
          ].map((tier, i) => {
            const Icon = tier.Icon;
            const current = isCurrent(tier.key);
            return (
              <motion.div
                key={tier.key}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07, ease: [0.16, 1, 0.3, 1] }}
                className={`relative flex flex-col p-6 bg-ink-950 ${
                  tier.featured ? "ring-1 ring-iris/40 z-10" : ""
                } ${"internal" in tier ? "ring-1 ring-red-400/20" : ""}`}
              >
                {tier.featured && (
                  <div className="absolute -top-px left-6 right-6 h-px bg-gradient-to-r from-transparent via-iris to-transparent" />
                )}
                {tier.featured && (
                  <div className="absolute inset-0 bg-gradient-to-b from-iris/[0.04] to-transparent pointer-events-none" />
                )}
                {(() => {
                  let badge: { label: string; cls: string } | null = null;
                  if ("internal" in tier) {
                    badge = {
                      label: current ? "Active / Staff" : "Staff Only",
                      cls: "text-red-400 bg-red-400/10 border-red-400/20",
                    };
                  } else if (current) {
                    badge = { label: "Active", cls: "text-iris bg-iris/10 border-iris/20" };
                  } else if (tier.featured) {
                    badge = { label: "Popular", cls: "text-iris bg-iris/10 border-iris/20" };
                  }
                  if (!badge) return null;
                  return (
                    <div className="absolute top-4 right-4">
                      <span className={`font-mono text-[8px] uppercase tracking-[0.18em] border px-2 py-0.5 ${badge.cls}`}>
                        {badge.label}
                      </span>
                    </div>
                  );
                })()}

                <div className="flex items-center gap-2 mb-5">
                  <Icon size={15} strokeWidth={1.5} className={"iconClass" in tier ? (tier as {iconClass: string}).iconClass : tier.accentClass} />
                  <span className={`font-mono text-[11px] uppercase tracking-[0.16em] ${tier.accentClass}`}>
                    {tier.label}
                  </span>
                </div>

                <div className="mb-5">
                  <div className="flex items-baseline gap-1.5">
                    <span className={`font-display text-3xl ${tier.featured ? "text-ink-50" : "text-ink-200"}`}>
                      {tier.price}
                    </span>
                    <span className="font-mono text-[11px] text-ink-600">{tier.period}</span>
                  </div>
                  <p className="font-mono text-[11px] text-ink-500 mt-2 leading-relaxed">{tier.desc}</p>
                </div>

                <ul className="flex-1 space-y-2.5 mb-7">
                  {tier.features.map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <Check
                        size={12}
                        strokeWidth={2.5}
                        className={`shrink-0 mt-0.5 ${"internal" in tier ? "text-red-400" : tier.featured ? "text-violet-400" : "text-signal-sage"}`}
                      />
                      <span className="font-mono text-[11px] text-ink-300 leading-relaxed">{f}</span>
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => {
                    if (tier.key === "free" || "internal" in tier) return;
                    if (tier.key === "pro") handleCheckout();
                    else window.open(`mailto:hello@prooflayer.cloud?subject=ProofLayer ${tier.label} inquiry`, "_blank");
                  }}
                  disabled={tier.key === "free" || "internal" in tier || (current && tier.key === "pro") || (tier.key === "pro" && checkoutLoading)}
                  aria-label={`${tier.label} plan CTA`}
                  className={`w-full py-3 font-mono text-[11px] uppercase tracking-[0.14em] transition-all cursor-pointer ${
                    tier.key === "free"
                      ? "border border-ink-800 text-ink-700 cursor-default"
                      : "internal" in tier
                      ? "border border-red-400/30 text-red-400/60 cursor-default"
                      : tier.featured
                      ? current
                        ? "border border-iris/40 text-iris/60 cursor-default"
                        : "bg-iris hover:bg-iris-light text-white"
                      : tier.key === "education"
                      ? "border border-signal-sage/40 text-signal-sage hover:bg-signal-sage/10"
                      : "border border-signal-amber/40 text-signal-amber hover:bg-signal-amber/10"
                  } disabled:opacity-40 disabled:cursor-default`}
                >
                  {"internal" in tier
                    ? "System Access"
                    : tier.key === "pro" && checkoutLoading
                    ? "Redirecting..."
                    : current
                    ? "Current plan"
                    : tier.key === "free"
                    ? "Free forever"
                    : tier.key === "pro"
                    ? isAuthenticated ? "Subscribe →" : "Get Pro →"
                    : <span className="flex items-center justify-center gap-1.5"><Mail size={11} strokeWidth={1.5} />Contact Sales</span>
                  }
                </button>
              </motion.div>
            );
          })}
        </div>

        {/* ── Feature comparison table ── */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.35 }}
          className="mt-12 border border-white/5"
        >
          <div className="px-6 py-4 border-b border-white/5 bg-white/[0.015]">
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-500">
              Full feature comparison
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[540px]">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="text-left px-6 py-3 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-600 font-normal w-1/3">
                    Feature
                  </th>
                  {[
                    { label: "Free", cls: "text-ink-400" },
                    { label: "Pro", cls: "text-iris" },
                    { label: "Education", cls: "text-signal-sage" },
                    { label: "Enterprise", cls: "text-signal-amber" },
                  ].map((h) => (
                    <th key={h.label} className={`px-4 py-3 font-mono text-[10px] uppercase tracking-[0.14em] font-normal text-center ${h.cls}`}>
                      {h.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {FEATURES_GRID.map((row, ri) => (
                  <tr
                    key={row.label}
                    className={`border-b border-white/[0.03] ${ri % 2 === 0 ? "" : "bg-white/[0.01]"}`}
                  >
                    <td className="px-6 py-3 font-mono text-[11px] text-ink-400">{row.label}</td>
                    <td className="px-4 py-3 text-center"><Cell val={row.free} /></td>
                    <td className="px-4 py-3 text-center"><Cell val={row.pro} /></td>
                    <td className="px-4 py-3 text-center"><Cell val={row.edu} /></td>
                    <td className="px-4 py-3 text-center"><Cell val={row.ent} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>

        {/* ── FAQ strip ── */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.45 }}
          className="mt-12 grid md:grid-cols-3 gap-px bg-white/5 border border-white/5"
        >
          {[
            { q: "Can I cancel anytime?", a: "Yes. Cancel from the billing portal and you keep access until the period ends." },
            { q: "Is there a free trial?", a: "The Free plan is permanent — 50 submissions/month, forever. No card required." },
            { q: "What payment methods?", a: "Cards, PayPal, and local methods via Paddle. Secure checkout, no data stored by us." },
          ].map(({ q, a }) => (
            <div key={q} className="p-6 bg-ink-950">
              <div className="font-mono text-[11px] text-ink-200 mb-2">{q}</div>
              <div className="font-mono text-[11px] text-ink-500 leading-relaxed">{a}</div>
            </div>
          ))}
        </motion.div>

        {/* ── Footer (public only) ── */}
        {!isAuthenticated && (
          <div className="mt-14 flex flex-wrap items-center justify-center gap-x-8 gap-y-2 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-700">
            <Link to="/terms" className="hover:text-ink-400 transition">Terms</Link>
            <Link to="/privacy" className="hover:text-ink-400 transition">Privacy</Link>
            <Link to="/refund" className="hover:text-ink-400 transition">Refund Policy</Link>
            <a href="mailto:hello@prooflayer.cloud" className="hover:text-ink-400 transition">hello@prooflayer.cloud</a>
          </div>
        )}
      </div>
    </div>
  );
}
