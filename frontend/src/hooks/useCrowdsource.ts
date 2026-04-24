import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { crowdsource } from "../api/endpoints";

export function useVoteStats(submissionId: string | null) {
  return useQuery({
    queryKey: ["voteStats", submissionId],
    queryFn: () => crowdsource.stats(submissionId!).then((r) => r.data),
    enabled: !!submissionId,
  });
}

export function useCastVote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { submission: string; value: string }) =>
      crowdsource.vote(data).then((r) => r.data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["voteStats", variables.submission] });
    },
  });
}
