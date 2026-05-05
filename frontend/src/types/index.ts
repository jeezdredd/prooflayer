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
  source_type: "phash_match" | "tineye" | "google_vision" | "c2pa";
  source_url: string;
  title: string;
  similarity_score: number | null;
  raw_data: Record<string, unknown>;
  found_at: string;
}

export interface FactCheckClaim {
  claim: string;
  assessment: "likely_true" | "likely_false" | "uncertain";
  explanation: string;
  fact_checks: Array<{
    claim_text: string;
    rating: string;
    url: string;
    publisher: string;
  }>;
}

export interface FactCheckResult {
  claims_count: number;
  overall_verdict: "mostly_accurate" | "mixed" | "misleading" | "no_claims";
  claims: FactCheckClaim[];
}
