import client from "./client";
import type {
  ApiKey,
  BillingInterval,
  PlanInfo,
  PlanKey,
  ClassroomHub,
  OrgTeacher,
  Organization,
  ClassMember,
  ClassStats,
  ClassRadar,
  ShadowSet,
  ShadowSetDetail,
  ClassSubmission,
  ClassBatch,
  Classroom,
  BatchDetail,
  ApiKeyCreated,
  FactCheckStatus,
  PaginatedResponse,
  ProvenanceResult,
  PublicSubmission,
  Report,
  Submission,
  SubmissionListItem,
  SubscriptionInfo,
  User,
  VerdictObjection,
  ObjectionDecision,
  ObjectionStatus,
  Vote,
  VoteStats,
} from "../types";
import { TERMS_VERSION } from "../legal";
import type { PaddleConfig } from "../billing/paddle";

export interface RegisterPayload {
  email: string;
  username: string;
  password: string;
  password_confirm: string;
  accept_terms: true;
  is_adult: boolean;
  allow_training?: boolean;
  language?: "en" | "ru";
}

export const auth = {
  register: (data: RegisterPayload) =>
    client.post<{ user: User; access: string }>("/auth/register/", data),

  login: (data: { email: string; password: string }) =>
    client.post<{ access: string }>("/auth/login/", data),

  refresh: () => client.post<{ access: string }>("/auth/refresh/", {}),

  logout: () => client.post<{ detail: string }>("/auth/logout/", {}),

  me: () => client.get<User>("/auth/me/"),

  updateMe: (data: Partial<User>) => client.patch<User>("/auth/me/", data),

  acceptTerms: (isAdult: boolean) =>
    client.post<User>("/auth/accept-terms/", { version: TERMS_VERSION, is_adult: isAdult }),

  deleteMe: (password: string, forgetTraining: boolean) =>
    client.delete("/auth/me/", { data: { password, forget_training: forgetTraining } }),

  verifyEmail: (token: string) =>
    client.post<{ detail: string; email?: string }>("/auth/verify-email/", { token }),

  requestPasswordReset: (email: string) =>
    client.post<{ detail: string }>("/auth/password-reset/", { email }),

  confirmPasswordReset: (uid: string, token: string, password: string) =>
    client.post<{ detail: string }>("/auth/password-reset/confirm/", { uid, token, password }),

  unsubscribe: (token: string) =>
    client.post<{ detail: string; email: string }>("/auth/unsubscribe/", { token }),

  resendVerification: () =>
    client.post<{ detail: string; delivery: string }>("/auth/resend-verification/", {}),
};

export const content = {
  upload: (file: File, onProgress?: (progress: number) => void, classroom?: string | null, student?: number | null) => {
    const formData = new FormData();
    formData.append("file", file);
    if (classroom) formData.append("classroom", classroom);
    if (student) formData.append("student", String(student));
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
  plans: () => client.get<{ plans: PlanInfo[]; intervals: BillingInterval[]; paddle: PaddleConfig | null }>("/billing/plans/"),
  checkout: (plan: PlanKey, interval: BillingInterval) => client.post<{ url: string; transaction_id: string }>("/billing/checkout/", { plan, interval }),
  portal: () => client.post<{ url: string }>("/billing/portal/", {}),
};

export const reanalyzeSubmission = (id: string) =>
  client.post<{ id: string; status: string }>(`/content/submissions/${id}/reanalyze/`, {});

export const togglePublic = (id: string, sensitive = false) =>
  client.post<{ is_public: boolean; is_sensitive: boolean }>(
    `/content/submissions/${id}/toggle-public/`,
    sensitive ? { sensitive: true } : {},
  );

export const objections = {
  create: (submissionId: string, reason: string) =>
    client.post<VerdictObjection>(`/content/submissions/${submissionId}/objection/`, { reason }),
  list: (params?: { status?: ObjectionStatus; page_size?: number }) =>
    client.get<PaginatedResponse<VerdictObjection>>("/content/objections/", { params }),
  respond: (id: string, decision: ObjectionDecision, response: string) =>
    client.post<VerdictObjection>(`/content/objections/${id}/respond/`, { decision, response }),
};

export const apiKeys = {
  list: () => client.get<ApiKey[]>("/auth/api-keys/"),
  create: (data: { name: string; webhook_url?: string }) => client.post<ApiKeyCreated>("/auth/api-keys/", data),
  revoke: (id: number) => client.delete(`/auth/api-keys/${id}/`),
};

export const batches = {
  create: (files: File[], name = "", classroom?: string | null, student?: number | null, students?: Record<string, number | null>) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    if (name) form.append("name", name);
    if (classroom) form.append("classroom", classroom);
    if (student) form.append("student", String(student));
    if (students && Object.keys(students).length > 0) form.append("students", JSON.stringify(students));
    return client.post<BatchDetail>("/content/batches/", form, { headers: { "Content-Type": "multipart/form-data" } });
  },
  detail: (id: string) => client.get<BatchDetail>(`/content/batches/${id}/`),
  exportCsv: (id: string, lang?: string) =>
    client.get<Blob>(`/content/batches/${id}/export.csv/`, { responseType: "blob", params: lang ? { lang } : undefined }),
};

export const classrooms = {
  list: () => client.get<Classroom[]>("/classroom/classrooms/"),
  create: (name: string) => client.post<Classroom>("/classroom/classrooms/", { name }),
  detail: (id: string) => client.get<Classroom>(`/classroom/classrooms/${id}/`),
  update: (id: string, data: Partial<Pick<Classroom, "name" | "archived" | "level">>) => client.patch<Classroom>(`/classroom/classrooms/${id}/`, data),
  join: (code: string, name?: string) => client.post<Classroom>("/classroom/join/", name ? { code, name } : { code }),
  leave: (id: string) => client.post(`/classroom/classrooms/${id}/leave/`, {}),
  rotateCode: (id: string) => client.post<{ join_code: string }>(`/classroom/classrooms/${id}/rotate-code/`, {}),
  roster: (id: string) => client.get<ClassMember[]>(`/classroom/classrooms/${id}/roster/`),
  removeMember: (id: string, userId: number) => client.delete(`/classroom/classrooms/${id}/members/${userId}/`),
  submissions: (id: string, params?: { student?: number; verdict?: string }) =>
    client.get<ClassSubmission[]>(`/classroom/classrooms/${id}/submissions/`, { params }),
  stats: (id: string) => client.get<ClassStats>(`/classroom/classrooms/${id}/stats/`),
  shadows: (id: string) => client.get<ShadowSet[]>(`/classroom/classrooms/${id}/shadows/`),
  createShadow: (id: string, prompt: string, target: number) => client.post<ShadowSet>(`/classroom/classrooms/${id}/shadows/`, { prompt, target }),
  shadowDetail: (id: string, shadowId: string) => client.get<ShadowSetDetail>(`/classroom/classrooms/${id}/shadows/${shadowId}/`),
  deleteShadow: (id: string, shadowId: string) => client.delete(`/classroom/classrooms/${id}/shadows/${shadowId}/`),
  radar: (id: string, days?: number) => client.get<ClassRadar>(`/classroom/classrooms/${id}/radar/`, { params: days ? { days } : undefined }),
  batches: (id: string) => client.get<ClassBatch[]>(`/classroom/classrooms/${id}/batches/`),
  exportCsv: (id: string, lang?: string) =>
    client.get<Blob>(`/classroom/classrooms/${id}/export.csv/`, { responseType: "blob", params: lang ? { lang } : undefined }),
};

export const orgs = {
  hub: () => client.get<ClassroomHub>("/classroom/hub/"),
  create: (name: string, slug: string, myName?: string) =>
    client.post<Organization>("/classroom/orgs/", myName ? { name, slug, my_name: myName } : { name, slug }),
  detail: (slug: string) => client.get<Organization>(`/classroom/orgs/${slug}/`),
  remove: (slug: string, password: string) => client.delete(`/classroom/orgs/${slug}/`, { data: { password } }),
  joinAsTeacher: (slug: string, code: string, name?: string) =>
    client.post<Organization>(`/classroom/orgs/${slug}/join-teacher/`, name ? { code, name } : { code }),
  rotateTeacherCode: (slug: string) => client.post<{ teacher_code: string }>(`/classroom/orgs/${slug}/rotate-teacher-code/`, {}),
  teachers: (slug: string) => client.get<OrgTeacher[]>(`/classroom/orgs/${slug}/teachers/`),
  removeTeacher: (slug: string, userId: number) => client.delete(`/classroom/orgs/${slug}/teachers/${userId}/`),
  classes: (slug: string) => client.get<Classroom[]>(`/classroom/orgs/${slug}/classes/`),
  createClass: (slug: string, name: string, level: number | null) =>
    client.post<Classroom>(`/classroom/orgs/${slug}/classes/`, { name, level }),
  updateSettings: (slug: string, data: { web_search_enabled: boolean }) =>
    client.patch<Organization>(`/classroom/orgs/${slug}/settings/`, data),
};
