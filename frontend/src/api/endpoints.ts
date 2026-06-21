import client from "./client";
import type {
  FactCheckStatus,
  PaginatedResponse,
  ProvenanceResult,
  PublicSubmission,
  Report,
  Submission,
  SubmissionListItem,
  SubscriptionInfo,
  User,
  Vote,
  VoteStats,
} from "../types";

export const auth = {
  register: (data: { email: string; username: string; password: string; password_confirm: string }) =>
    client.post<{ user: User; access: string }>("/auth/register/", data),

  login: (data: { email: string; password: string }) =>
    client.post<{ access: string }>("/auth/login/", data),

  refresh: () => client.post<{ access: string }>("/auth/refresh/", {}),

  logout: () => client.post<{ detail: string }>("/auth/logout/", {}),

  me: () => client.get<User>("/auth/me/"),

  updateMe: (data: Partial<User>) => client.patch<User>("/auth/me/", data),

  verifyEmail: (token: string) =>
    client.post<{ detail: string; email?: string }>("/auth/verify-email/", { token }),

  resendVerification: () =>
    client.post<{ detail: string; delivery: string }>("/auth/resend-verification/", {}),
};

export const content = {
  upload: (file: File, onProgress?: (progress: number) => void) => {
    const formData = new FormData();
    formData.append("file", file);
    return client.post<Submission>("/content/submissions/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      },
    });
  },

  list: (params?: Record<string, string>) =>
    client.get<PaginatedResponse<SubmissionListItem>>("/content/submissions/", { params }),

  detail: (id: string) => client.get<Submission>(`/content/submissions/${id}/`),

  compare: (ids: [string, string]) =>
    client.get<Submission[]>(`/content/submissions/compare/`, { params: { ids: ids.join(",") } }),

  delete: (id: string) => client.delete(`/content/submissions/${id}/`),

  stats: () =>
    client.get<{
      total: number;
      by_verdict: Record<string, number>;
      by_status: Record<string, number>;
      avg_score: number | null;
      known_fake_hits: number;
    }>(`/content/submissions/stats/`),
};

export const crowdsource = {
  vote: (data: { submission: string; value: string }) =>
    client.post<Vote>("/crowdsource/votes/", data),

  stats: (submissionId: string) =>
    client.get<VoteStats>(`/crowdsource/votes/stats/${submissionId}/`),
};

export const reports = {
  create: (data: { submission: string; reason: string; description?: string }) =>
    client.post<Report>("/reports/", data),
};

export const provenance = {
  list: (submissionId: string) =>
    client.get<ProvenanceResult[]>(`/provenance/${submissionId}/`),
};

export const feedback = {
  submit: (data: { category: string; message: string; contact_email?: string }) =>
    client.post<{ detail: string; id: string }>("/system/feedback/", data),
};

export const factcheck = {
  check: (text: string) =>
    client.post<{ task_id: string }>("/factcheck/check/", { text }),
  status: (task_id: string) =>
    client.get<FactCheckStatus>(`/factcheck/status/${task_id}/`),
  fetchUrl: (url: string) =>
    client.post<{ text: string; title: string }>("/factcheck/fetch-url/", { url }),
  extractDoc: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return client.post<{ text: string }>("/factcheck/extract-doc/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  exportPdf: (result: unknown, text: string) =>
    client.post<Blob>(
      "/factcheck/export/",
      { result, text },
      { responseType: "blob" },
    ),
};

export const review = {
  queue: (params?: Record<string, string>) =>
    client.get<PaginatedResponse<SubmissionListItem & { submitter_email: string; override_count: number }>>(
      "/content/review/queue/",
      { params },
    ),
  override: (id: string, data: { verdict: string; reason: string }) =>
    client.post(`/content/review/${id}/override/`, data),
};

export const retrain = {
  trigger: (media_type: "image" | "video" | "audio" = "image", force = false, epochs?: number) =>
    client.post<{ task_id: string; media_type: string; force: boolean; epochs: number | null }>(
      "/analyzers/retrain/",
      { media_type, force, ...(epochs ? { epochs } : {}) },
    ),
  runs: () =>
    client.get<Array<{
      id: string;
      media_type: string;
      status: string;
      samples_used: number;
      hf_revision: string;
      error: string;
      started_at: string | null;
      finished_at: string | null;
    }>>("/analyzers/retrain/runs/"),
};

export const feed = {
  list: (params?: Record<string, string>) =>
    client.get<PaginatedResponse<PublicSubmission>>("/content/feed/", { params }),
  detail: (id: string) => client.get<PublicSubmission>(`/content/feed/${id}/`),
};

export const billing = {
  subscription: () => client.get<SubscriptionInfo>("/billing/subscription/"),
  checkout: () => client.post<{ url: string }>("/billing/checkout/", {}),
  portal: () => client.post<{ url: string }>("/billing/portal/", {}),
};

export const togglePublic = (id: string) =>
  client.post<{ is_public: boolean }>(`/content/submissions/${id}/toggle-public/`, {});
