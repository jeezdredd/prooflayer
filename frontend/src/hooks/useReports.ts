import { useMutation } from "@tanstack/react-query";
import { reports } from "../api/endpoints";

export function useCreateReport() {
  return useMutation({
    mutationFn: (data: { submission: string; reason: string; description?: string }) =>
      reports.create(data).then((r) => r.data),
  });
}
