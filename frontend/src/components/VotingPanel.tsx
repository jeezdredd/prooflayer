import clsx from "clsx";
import { motion } from "motion/react";
import { Check, X, HelpCircle } from "lucide-react";
import { useVoteStats, useCastVote } from "../hooks/useCrowdsource";
import { toast } from "./ui/Toast";

interface VotingPanelProps {
  submissionId: string;
  fileUrl?: string | null;
}

const VOTE_OPTIONS = [
  { value: "real", label: "Real", Icon: Check, accent: "sage" },
  { value: "fake", label: "Fake", Icon: X, accent: "blood" },
  { value: "uncertain", label: "Uncertain", Icon: HelpCircle, accent: "amber" },
] as const;

export default function VotingPanel({ submissionId, fileUrl }: VotingPanelProps) {
  const { data: stats } = useVoteStats(submissionId);
  const { mutate: castVote, isPending } = useCastVote();

  const counts: Record<string, number> = {
    real: stats?.real_count ?? 0,
    fake: stats?.fake_count ?? 0,
    uncertain: stats?.uncertain_count ?? 0,
  };

  return (
    <div className="case-card crop-marks mt-4 p-6">
      {fileUrl && (
        <div className="mb-5 flex justify-center">
          <img
            src={fileUrl}
            alt="Submission"
            className="max-h-72 max-w-full rounded-sm object-contain border border-white/10 bg-ink-950/40"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        </div>
      )}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <span className="w-1.5 h-1.5 rounded-full bg-signal-cyan pulse-dot" />
          <span className="label-mono">Community Verdict</span>
        </div>
        {stats && (
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500 ticker">
            {stats.total} vote{stats.total !== 1 ? "s" : ""}
          </span>
        )}
      </div>
      <div className="grid grid-cols-3 gap-3">
        {VOTE_OPTIONS.map(({ value, label, Icon, accent }) => {
          const isActive = stats?.user_vote === value;
          const activeRing =
            accent === "sage" ? "ring-signal-sage text-signal-sage bg-signal-sage/10" :
            accent === "blood" ? "ring-signal-blood text-signal-blood bg-signal-blood/10" :
            "ring-signal-amber text-signal-amber bg-signal-amber/10";
          return (
            <motion.button
              key={value}
              whileTap={{ scale: 0.97 }}
              onClick={() =>
                castVote(
                  { submission: submissionId, value },
                  {
                    onSuccess: () => toast.success(`Voted "${label}"`),
                    onError: () => toast.error("Vote failed"),
                  },
                )
              }
              disabled={isPending}
              className={clsx(
                "flex flex-col items-center gap-2 py-4 rounded-sm transition-all font-mono text-[11px] uppercase tracking-[0.14em]",
                "ring-1",
                isActive ? activeRing : "ring-white/10 bg-white/[0.02] text-ink-300 hover:ring-white/25 hover:text-ink-100",
                isPending && "opacity-50 cursor-not-allowed",
              )}
            >
              <Icon size={16} strokeWidth={1.5} />
              <span>{label}</span>
              <span className="font-display text-2xl text-current ticker leading-none">{counts[value]}</span>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
