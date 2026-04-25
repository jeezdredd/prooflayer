import { useQuery } from "@tanstack/react-query";
import { provenance } from "../api/endpoints";

export function useProvenance(submissionId: string | null) {
  return useQuery({
    queryKey: ["provenance", submissionId],
    queryFn: () => provenance.list(submissionId!).then((r) => r.data),
    enabled: !!submissionId,
    staleTime: 60_000,
  });
}
