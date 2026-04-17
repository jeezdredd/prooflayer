import { useMutation, useQuery } from "@tanstack/react-query";
import { content } from "../api/endpoints";
import { useUploadStore } from "../stores/uploadStore";

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
    onError: (err: Error) => {
      setError(err.message);
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
      return 2000;
    },
  });
}

export function useSubmissions() {
  return useQuery({
    queryKey: ["submissions"],
    queryFn: () => content.list().then((r) => r.data),
  });
}
