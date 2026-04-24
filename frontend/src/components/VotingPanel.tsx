import clsx from "clsx";
import { useVoteStats, useCastVote } from "../hooks/useCrowdsource";

interface VotingPanelProps {
  submissionId: string;
}

const VOTE_OPTIONS = [
  { value: "real", label: "Real", color: "green" },
  { value: "fake", label: "Fake", color: "red" },
  { value: "uncertain", label: "Uncertain", color: "gray" },
] as const;

export default function VotingPanel({ submissionId }: VotingPanelProps) {
  const { data: stats } = useVoteStats(submissionId);
  const { mutate: castVote, isPending } = useCastVote();

  const counts: Record<string, number> = {
    real: stats?.real_count ?? 0,
    fake: stats?.fake_count ?? 0,
    uncertain: stats?.uncertain_count ?? 0,
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 mt-4">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-sm font-semibold text-gray-700">Community Verdict</h4>
        {stats && (
          <span className="text-xs text-gray-400">{stats.total} vote{stats.total !== 1 ? "s" : ""}</span>
        )}
      </div>
      <div className="flex gap-3">
        {VOTE_OPTIONS.map(({ value, label, color }) => {
          const isActive = stats?.user_vote === value;
          return (
            <button
              key={value}
              onClick={() => castVote({ submission: submissionId, value })}
              disabled={isPending}
              className={clsx(
                "flex-1 flex flex-col items-center gap-1 py-3 rounded-lg border-2 transition-colors text-sm font-medium",
                {
                  "border-green-500 bg-green-50 text-green-700": isActive && color === "green",
                  "border-red-500 bg-red-50 text-red-700": isActive && color === "red",
                  "border-gray-500 bg-gray-100 text-gray-700": isActive && color === "gray",
                  "border-gray-200 bg-white text-gray-600 hover:border-gray-400": !isActive,
                  "opacity-50 cursor-not-allowed": isPending,
                }
              )}
            >
              <span>{label}</span>
              <span className="text-xs font-normal text-gray-500">{counts[value]}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
