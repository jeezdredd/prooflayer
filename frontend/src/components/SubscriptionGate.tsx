import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { Zap, LayoutDashboard } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { billing } from "../api/endpoints";

interface Props {
  children: React.ReactNode;
  feature?: string;
}

export function useSubscriptionInfo() {
  return useQuery({
    queryKey: ["subscription"],
    queryFn: () => billing.subscription().then((r) => r.data),
    staleTime: 60_000,
  });
}

export default function SubscriptionGate({ children, feature }: Props) {
  const { data: sub, isLoading } = useSubscriptionInfo();

  if (isLoading) return null;

  const isPro = sub && sub.tier !== "free";
  if (isPro) return <>{children}</>;

  return (
    <motion.div
      className="case-card crop-marks p-10 max-w-xl mx-auto text-center"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="flex justify-center mb-5">
        <div className="w-14 h-14 border border-iris/50 bg-iris/10 flex items-center justify-center rounded-sm">
          <Zap className="w-7 h-7 text-iris" />
        </div>
      </div>
      <span className="label-mono">Pro Feature</span>
      <h1 className="font-display text-3xl text-white mt-3">
        Upgrade to Pro
      </h1>
      <p className="text-sm text-ink-400 mt-3 leading-relaxed">
        {feature
          ? <><span className="font-mono text-ink-200">{feature}</span> requires a Pro subscription.</>
          : "This feature requires a Pro subscription."}
        {" "}Upgrade for $12/month to unlock all features.
      </p>
      {sub && (
        <p className="text-xs text-ink-600 font-mono mt-2">
          {sub.uploads_used} / {sub.uploads_limit} uploads used this month
        </p>
      )}
      <div className="mt-7 flex items-center justify-center gap-3 flex-wrap">
        <Link
          to="/pricing"
          className="inline-flex items-center gap-2 bg-iris hover:bg-iris-light text-white px-5 py-2.5 text-xs font-mono uppercase tracking-[0.14em] transition"
        >
          <Zap className="w-3.5 h-3.5" />
          View Pricing
        </Link>
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-2 border border-ink-700 text-ink-300 px-5 py-2.5 text-xs font-mono uppercase tracking-[0.14em] hover:bg-ink-800 hover:text-ink-100 transition"
        >
          <LayoutDashboard className="w-3.5 h-3.5" />
          Back to Dashboard
        </Link>
      </div>
    </motion.div>
  );
}
