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
  created_at: string;
  updated_at: string;
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

export interface SubscriptionInfo {
  tier: "free" | "pro" | "education" | "enterprise";
  status: "active" | "past_due" | "cancelled" | "trialing";
  uploads_used: number;
  uploads_limit: number;
  can_use_vlm: boolean;
  can_download_pdf: boolean;
  can_compare: boolean;
  can_embed: boolean;
  can_api: boolean;
  stripe_subscription_id: string;
  current_period_end: string | null;
}
