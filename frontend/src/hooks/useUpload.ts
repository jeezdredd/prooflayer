import { useMutation, useQuery } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { content } from "../api/endpoints";
import { useUploadStore } from "../stores/uploadStore";
import { toast } from "../components/ui/Toast";
import { t } from "../i18n";
import type { Submission } from "../types";

export function useUploadFile() {
  const { setProgress, setSubmissionId, setStatus, setError } = useUploadStore();

  return useMutation({
    mutationFn: ({ file, classroom }: { file: File; classroom?: string | null }) => {
      setStatus("uploading");
      return content.upload(file, setProgress, classroom);
    },
    onSuccess: (res) => {
      setSubmissionId(res.data.id);
      setStatus("processing");
    },
    onError: (err: unknown) => {
      if (err instanceof AxiosError && err.response?.status === 402) {
        const code = err.response.data?.code;
        if (code === "upload_limit_reached") {
          const limitText = t("Monthly upload limit reached. Upgrade to Pro for more.");
          setError(limitText);
          toast.error(limitText);
          return;
        }
      }
      setError(err instanceof Error ? err.message : t("Upload failed"));
    },
  });
}

const MAP_WAIT_MS = 5 * 60 * 1000;

export function mapPending(data: Submission): boolean {
  if (data.status !== "completed") return false;
  const expected = data.expected_analyzers?.some((a) => a.name === "manipulation_map");
  const done = data.analysis_results?.some((r) => r.analyzer_name === "manipulation_map");
  const since = Date.now() - Date.parse(data.updated_at);
  return !!expected && !done && since < MAP_WAIT_MS;
}

export function useSubmissionDetail(id: string | null) {
  return useQuery({
    queryKey: ["submission", id],
    queryFn: () => content.detail(id!).then((r) => r.data),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === "completed" || data.status === "failed")) {
        const originality = data.originality?.status;
        return originality === "pending" || originality === "running" || mapPending(data) ? 5000 : false;
      }
      return 3000;
    },
  });
}

export function useSubmissions() {
  return useQuery({
    queryKey: ["submissions"],
    queryFn: () => content.list().then((r) => r.data),
  });
}
