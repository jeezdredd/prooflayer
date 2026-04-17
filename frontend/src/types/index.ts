export interface User {
  id: number;
  email: string;
  username: string;
  avatar: string;
  bio: string;
  is_verified: boolean;
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

export interface Submission {
  id: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  sha256_hash: string;
  status: "pending" | "processing" | "completed" | "failed";
  metadata: Record<string, unknown>;
  final_score: number | null;
  final_verdict: string;
  is_known_fake: boolean;
  analysis_results: AnalysisResult[];
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
  created_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
