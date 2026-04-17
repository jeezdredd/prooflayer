import { create } from "zustand";

interface UploadState {
  progress: number;
  submissionId: string | null;
  status: "idle" | "uploading" | "processing" | "done" | "error";
  error: string | null;
  setProgress: (progress: number) => void;
  setSubmissionId: (id: string) => void;
  setStatus: (status: UploadState["status"]) => void;
  setError: (error: string) => void;
  reset: () => void;
}

export const useUploadStore = create<UploadState>((set) => ({
  progress: 0,
  submissionId: null,
  status: "idle",
  error: null,

  setProgress: (progress) => set({ progress }),
  setSubmissionId: (id) => set({ submissionId: id }),
  setStatus: (status) => set({ status }),
  setError: (error) => set({ error, status: "error" }),
  reset: () => set({ progress: 0, submissionId: null, status: "idle", error: null }),
}));
