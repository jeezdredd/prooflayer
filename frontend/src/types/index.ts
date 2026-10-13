export interface User {
  id: number;
  email: string;
  username: string;
  avatar: string;
  bio: string;
  is_verified: boolean;
  is_staff: boolean;
  date_joined: string;
}

export interface Tokens {
  access: string;
  refresh: string;
}

export interface AuthResponse {
  user: User;
  tokens: Tokens;
}

export interface AnalysisResult {
  id: string;
  analyzer_name: string;
  confidence: number;
  verdict: string;
  evidence: Record<string, unknown>;
  execution_time: number | null;
  error_message: string;
  created_at: string;
}

export interface ExpectedAnalyzer {
  name: string;
  description: string;
}

export interface Submission {
  id: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  sha256_hash: string;
  status: "pending" | "processing" | "completed" | "failed";
  status_message: string;
  metadata: Record<string, unknown>;
  final_score: number | null;
  final_verdict: string;
  is_known_fake: boolean;
  is_public: boolean;
  file_url: string | null;
  analysis_results: AnalysisResult[];
  expected_analyzers: ExpectedAnalyzer[];
  ensemble?: EnsembleInfo | null;
  created_at: string;
  updated_at: string;
}

export interface EnsembleInfo {
  name: string;
  version: string;
  label: string;
  fingerprint: string;
  current_version: string;
  current_fingerprint: string;
  is_current: boolean;
}

export interface SubmissionListItem {
  id: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  status: string;
  final_score: number | null;
  final_verdict: string;
  is_known_fake: boolean;
  thumbnail_url: string | null;
  created_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface VoteStats {
  submission_id: string;
  real_count: number;
  fake_count: number;
  uncertain_count: number;
  total: number;
  user_vote: "real" | "fake" | "uncertain" | null;
}

export interface Vote {
  id: string;
  submission: string;
  value: "real" | "fake" | "uncertain";
  created_at: string;
}

export interface Report {
  id: string;
  submission: string;
  reason: "fake_content" | "misleading" | "copyright" | "spam" | "other";
  description: string;
  status: "pending" | "reviewed" | "resolved" | "dismissed";
  created_at: string;
}

export interface ProvenanceResult {
  id: string;
  source_type: "phash_match" | "clip_neighbour" | "tineye" | "google_vision" | "c2pa";
  source_url: string;
  title: string;
  similarity_score: number | null;
  raw_data: Record<string, unknown>;
  found_at: string;
}

export interface FactCheckClaim {
  claim: string;
  assessment: "likely_true" | "likely_false" | "uncertain";
  confidence?: number;
  explanation: string;
  fact_checks: Array<{
    claim_text: string;
    rating: string;
    url: string;
    publisher: string;
  }>;
  sources?: Array<{ title: string; url: string }>;
  wikipedia?: { title: string; extract: string; url: string } | null;
}

export type FactCheckMode = "text" | "url" | "document";

export interface FactCheckResult {
  claims_count: number;
  overall_verdict: "mostly_accurate" | "mixed" | "misleading" | "no_claims";
  claims: FactCheckClaim[];
  entities?: Array<{ text: string; type: string; start: number; end: number }>;
}

export type FactCheckStage =
  | "pending"
  | "extracting"
  | "searching"
  | "assessing"
  | "cross_referencing"
  | "done"
  | "error";

export interface FactCheckStatus {
  stage: FactCheckStage;
  progress: number;
  result?: FactCheckResult;
  error?: string;
}

export interface UploaderProfile {
  username: string;
  date_joined: string;
  avatar_url: string | null;
}

export interface PublicSubmission {
  id: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  final_score: number | null;
  final_verdict: string;
  is_known_fake: boolean;
  thumbnail_url: string | null;
  uploader: UploaderProfile;
  analysis_results: AnalysisResult[];
  created_at: string;
}

export type PlanKey = "free" | "pro" | "education" | "university" | "enterprise";
export type BillingInterval = "month" | "year";

export interface PlanInfo {
  key: PlanKey;
  name: string;
  audience: string;
  monthly_usd: number;
  yearly_usd: number;
  uploads_per_month: number;
  api_per_minute: number;
  teacher_seats: number;
  schools: number;
  compare: boolean;
  embed: boolean;
  api: boolean;
  vlm: boolean;
  pdf: boolean;
  priority_support: boolean;
  sla: boolean;
  on_premise: boolean;
  self_serve: boolean;
  classroom: boolean;
  highlights: string[];
  checkout: Record<BillingInterval, boolean>;
}

export interface SubscriptionInfo {
  tier: PlanKey;
  status: "active" | "past_due" | "cancelled" | "trialing";
  uploads_used: number;
  uploads_limit: number;
  can_use_vlm: boolean;
  can_download_pdf: boolean;
  can_compare: boolean;
  can_embed: boolean;
  can_api: boolean;
  can_classroom: boolean;
  stripe_subscription_id: string;
  current_period_end: string | null;
}

export interface ApiKey {
  id: number;
  name: string;
  prefix: string;
  webhook_url: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  last_webhook_at: string | null;
  last_webhook_status: string;
}

export interface ApiKeyCreated extends ApiKey {
  key: string;
  webhook_secret: string;
}

export interface BatchItem {
  id: string;
  original_filename: string;
  mime_type: string;
  status: string;
  final_verdict: string;
  final_score: number | null;
  tribunal_version: string;
}

export interface BatchDetail {
  id: string;
  name: string;
  created_at: string;
  skipped: { name: string; reason: string }[];
  summary: { total: number; done: number; by_status: Record<string, number>; by_verdict: Record<string, number> };
  items: BatchItem[];
}

export interface Classroom {
  id: string;
  name: string;
  role: "teacher" | "student";
  join_code: string | null;
  owner_name: string;
  student_count: number;
  archived: boolean;
  created_at: string;
  organization_slug: string | null;
  organization_name: string | null;
}

export interface Organization {
  name: string;
  slug: string;
  role: "admin" | "teacher" | "student" | null;
  teacher_code?: string;
  plan_active?: boolean;
  teacher_seats?: number | null;
  teacher_seats_used?: number;
}

export interface OrgTeacher {
  user_id: number;
  username: string;
  email: string;
  role: "admin" | "teacher";
  classes: number;
  joined_at: string;
}

export interface ClassroomHub {
  organizations: Organization[];
  enrolled: Classroom[];
  personal_classes: Classroom[];
  can_create_organization: boolean;
}

export interface ClassMember {
  user_id: number;
  username: string;
  email: string;
  joined_at: string;
  total: number;
  flagged: number;
  last_submission_at: string | null;
}

export interface ClassSubmission {
  id: string;
  original_filename: string;
  mime_type: string;
  status: string;
  final_verdict: string;
  final_score: number | null;
  tribunal_version: string;
  created_at: string;
  student_id: number;
  student: string;
  words: number | null;
}

export interface ClassStats {
  students: number;
  total: number;
  completed: number;
  flagged: number;
  flagged_share: number;
  by_verdict: Record<string, number>;
  timeline: { date: string; total: number; flagged: number }[];
}
