import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Check, Zap, Building2, GraduationCap } from "lucide-react";
import { billing } from "../api/endpoints";
import { toast } from "../components/ui/Toast";

const TIERS = [
  {
    key: "free",
    label: "Free",
    price: "$0",
    period: "forever",
    description: "For individuals getting started with content verification.",
    Icon: Zap,
    color: "border-ink-700",
    headerColor: "text-ink-200",
    features: [
      "50 submissions / month",
      "All detection analyzers",
      "Community voting",
      "PDF reports",
    ],
    locked: [],
    cta: "Current plan",
    ctaStyle: "border border-ink-700 text-ink-500 cursor-default",
  },
  {
    key: "pro",
    label: "Pro",
    price: "$12",
    period: "/ month",
    description: "For journalists, researchers, and power users.",
    Icon: Zap,
    color: "border-iris/50",
    headerColor: "text-iris",
    features: [
      "500 submissions / month",
      "All detection analyzers",
      "Vision LLM analysis",
      "PDF reports",
      "Side-by-side compare",
      "Widget embed",
      "API access",
    ],
    locked: [],
    cta: "Subscribe",
    ctaStyle: "bg-iris hover:bg-iris-light text-white transition",
  },
  {
    key: "education",
    label: "Education",
    price: "Contact Sales",
    period: "",
    description: "For schools, universities, and non-profit organizations.",
    Icon: GraduationCap,
    color: "border-signal-sage/40",
    headerColor: "text-signal-sage",
    features: [
      "2000 submissions / month",
      "All Pro features",
      "Classroom dashboard",
      "Custom onboarding",
      "Priority support",
    ],
    locked: [],
    cta: "Contact Sales",
    ctaStyle: "border border-signal-sage/60 text-signal-sage hover:bg-signal-sage/10 transition",
  },
  {
    key: "enterprise",
    label: "Enterprise",
    price: "Contact Sales",
    period: "",
    description: "For media companies, newsrooms, and large organizations.",
    Icon: Building2,
    color: "border-signal-amber/40",
    headerColor: "text-signal-amber",
    features: [
      "Unlimited submissions",
      "All Pro features",
      "On-premise deployment option",
      "SLA guarantee",
      "Dedicated support",
      "Custom integrations",
      "Audit logs",
    ],
    locked: [],
    cta: "Contact Sales",
    ctaStyle: "border border-signal-amber/60 text-signal-amber hover:bg-signal-amber/10 transition",
  },
];

export default function PricingPage() {
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);

  const { data: sub } = useQuery({
    queryKey: ["subscription"],
    queryFn: () => billing.subscription().then((r) => r.data),
  });

  const handleCheckout = async () => {
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

  const handleContactSales = (tier: string) => {
    window.open(
      `mailto:hello@prooflayer.com?subject=ProofLayer ${tier} inquiry`,
      "_blank"
    );
  };

  return (
    <div>
      <div className="mb-10">
        <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-600 mb-3">
          Billing / Plans
        </div>
        <h1 className="font-display text-3xl text-ink-50 mb-2">Pricing</h1>
        <p className="text-ink-400 text-sm max-w-xl">
          All plans include full access to ProofLayer detectors. Upgrade for higher limits and advanced features.
        </p>
      </div>

      {sub && (
        <div className="mb-8 p-4 case-card flex items-center justify-between">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
              Current plan
            </span>
            <div className="font-mono text-sm text-ink-100 mt-1 capitalize">
              {sub.tier}{" "}
              <span className="text-ink-500">
                - {sub.uploads_used} / {sub.uploads_limit} uploads this month
              </span>
            </div>
          </div>
          {sub.tier === "pro" && (
            <button
              onClick={handlePortal}
              disabled={portalLoading}
              className="font-mono text-[10px] uppercase tracking-[0.14em] border border-ink-600 text-ink-400 hover:text-ink-200 hover:border-ink-400 px-3 py-1.5 transition disabled:opacity-50"
            >
              {portalLoading ? "..." : "Manage Billing"}
            </button>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {TIERS.map((tier, i) => {
          const Icon = tier.Icon;
          const isCurrent = sub?.tier === tier.key;
          return (
            <motion.div
              key={tier.key}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className={`case-card p-6 flex flex-col border ${tier.color} ${isCurrent ? "ring-1 ring-iris/30" : ""}`}
            >
              <div className="flex items-center gap-2 mb-4">
                <Icon size={16} strokeWidth={1.5} className={tier.headerColor} />
                <span className={`font-mono text-[11px] uppercase tracking-[0.14em] ${tier.headerColor}`}>
                  {tier.label}
                </span>
                {isCurrent && (
                  <span className="ml-auto font-mono text-[9px] uppercase tracking-[0.16em] text-iris bg-iris/10 px-2 py-0.5 rounded-full">
                    Active
                  </span>
                )}
              </div>

              <div className="mb-4">
                <span className="font-display text-2xl text-ink-50">{tier.price}</span>
                {tier.period && (
                  <span className="text-ink-500 text-sm ml-1">{tier.period}</span>
                )}
                <p className="text-ink-500 text-xs mt-2 leading-relaxed">{tier.description}</p>
              </div>

              <ul className="flex-1 space-y-2 mb-6">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <Check size={12} strokeWidth={2} className="text-signal-sage mt-0.5 shrink-0" />
                    <span className="font-mono text-[11px] text-ink-300">{f}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => {
                  if (isCurrent && tier.key === "pro") return;
                  if (tier.key === "pro") handleCheckout();
                  else if (tier.key === "education") handleContactSales("Education");
                  else if (tier.key === "enterprise") handleContactSales("Enterprise");
                }}
                disabled={
                  (tier.key === "free") ||
                  (isCurrent && tier.key !== "pro") ||
                  (tier.key === "pro" && checkoutLoading)
                }
                className={`w-full py-2.5 font-mono text-[11px] uppercase tracking-[0.14em] ${
                  isCurrent && tier.key === "free"
                    ? "border border-ink-700 text-ink-600 cursor-default"
                    : tier.ctaStyle
                } disabled:opacity-50`}
              >
                {tier.key === "pro" && checkoutLoading
                  ? "..."
                  : isCurrent
                  ? "Current plan"
                  : tier.cta}
              </button>
            </motion.div>
          );
        })}
      </div>

      <div className="mt-10 p-6 case-card border border-ink-800">
        <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 mb-3">
          Feature comparison
        </div>
        <div className="overflow-x-auto">
          <table className="w-full font-mono text-[11px]">
            <thead>
              <tr className="border-b border-ink-800">
                <th className="text-left py-2 text-ink-500 font-normal">Feature</th>
                <th className="text-center py-2 text-ink-400 font-normal">Free</th>
                <th className="text-center py-2 text-iris font-normal">Pro</th>
                <th className="text-center py-2 text-signal-sage font-normal">Education</th>
                <th className="text-center py-2 text-signal-amber font-normal">Enterprise</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-900">
              {[
                ["Submissions / month", "50", "500", "2000", "Unlimited"],
                ["All analyzers", "✓", "✓", "✓", "✓"],
                ["Vision LLM", "✓", "✓", "✓", "✓"],
                ["PDF reports", "✓", "✓", "✓", "✓"],
                ["Compare tool", "-", "✓", "✓", "✓"],
                ["Widget embed", "-", "✓", "✓", "✓"],
                ["API access", "-", "✓", "✓", "✓"],
                ["Priority support", "-", "-", "✓", "✓"],
                ["SLA", "-", "-", "-", "✓"],
              ].map(([feature, ...vals]) => (
                <tr key={feature} className="hover:bg-white/[0.01]">
                  <td className="py-2 text-ink-400">{feature}</td>
                  {vals.map((v, i) => (
                    <td key={i} className={`py-2 text-center ${v === "-" ? "text-ink-700" : "text-ink-200"}`}>
                      {v}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
