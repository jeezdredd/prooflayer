import { useMutation } from "@tanstack/react-query";
import { factcheck } from "../api/endpoints";

export function useFactCheck() {
  return useMutation({
    mutationFn: (text: string) => factcheck.check(text).then((r) => r.data),
  });
}
