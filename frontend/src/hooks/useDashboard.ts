import { useQuery } from "@tanstack/react-query";
import { content } from "../api/endpoints";

export function useDashboard(params: Record<string, string>) {
  return useQuery({
    queryKey: ["dashboard", params],
    queryFn: () => content.list(params).then((r) => r.data),
  });
}

export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => content.stats().then((r) => r.data),
    staleTime: 30_000,
  });
}
