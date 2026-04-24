import client from "./client";
import type {
  AuthResponse,
  PaginatedResponse,
  Report,
  Submission,
  SubmissionListItem,
  User,
  Vote,
  VoteStats,
} from "../types";

export const auth = {
  register: (data: { email: string; username: string; password: string; password_confirm: string }) =>
    client.post<AuthResponse>("/auth/register/", data),

  login: (data: { email: string; password: string }) =>
    client.post<{ access: string; refresh: string }>("/auth/login/", data),

  refresh: (refresh: string) =>
    client.post<{ access: string; refresh?: string }>("/auth/refresh/", { refresh }),

  me: () => client.get<User>("/auth/me/"),

  updateMe: (data: Partial<User>) => client.patch<User>("/auth/me/", data),
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

  delete: (id: string) => client.delete(`/content/submissions/${id}/`),
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
