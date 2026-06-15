import { useMutation, useQuery } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { content } from "../api/endpoints";
import { useUploadStore } from "../stores/uploadStore";
import { toast } from "../components/ui/Toast";

export function useUploadFile() {
  const { setProgress, setSubmissionId, setStatus, setError } = useUploadStore();

  return useMutation({
    mutationFn: (file: File) => {
      setStatus("uploading");
      return content.upload(file, setProgress);
    },
    onSuccess: (res) => {
      setSubmissionId(res.data.id);
      setStatus("processing");
    },
    onError: (err: unknown) => {
      if (err instanceof AxiosError && err.response?.status === 402) {
        const code = err.response.data?.code;
        if (code === "upload_limit_reached") {
          const msg = "Monthly upload limit reached. Upgrade to Pro for more.";
          setError(msg);
          toast.error(msg);
          return;
        }
      }
      setError(err instanceof Error ? err.message : "Upload failed");
    },
  });
}

export function useSubmissionDetail(id: string | null) {
  return useQuery({
    queryKey: ["submission", id],
    queryFn: () => content.detail(id!).then((r) => r.data),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === "completed" || data.status === "failed")) {
        return false;
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
