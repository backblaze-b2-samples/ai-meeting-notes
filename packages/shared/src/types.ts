// Shared TypeScript types — mirrors the Pydantic models on the backend.
// Keep this file in lockstep with `services/api/app/types/*.py`.

export type FileStatus = "uploading" | "complete" | "error";

export interface FileMetadata {
  key: string;
  filename: string;
  folder: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
}

export interface FileMetadataDetail {
  filename: string;
  size_bytes: number;
  size_human: string;
  mime_type: string;
  extension: string;
  md5: string;
  sha256: string;
  uploaded_at: string;
  duration_ms: number | null;
  sample_rate: number | null;
  channels: number | null;
  bit_depth: number | null;
  codec: string | null;
}

export interface FileUploadResponse {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
  metadata: FileMetadataDetail | null;
}

export interface DailyUploadCount {
  date: string;
  uploads: number;
  duration_ms: number;
}

export interface UploadStats {
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  uploads_today: number;
  total_downloads: number;
  total_meetings: number;
  total_duration_ms: number;
  meetings_size_bytes: number;
  meetings_size_human: string;
  open_action_items: number;
  meetings_by_state: Record<string, number>;
}

// --- Meetings ---

export type MeetingState =
  | "queued"
  | "transcribing"
  | "summarizing"
  | "done"
  | "failed";

export type PipelineStage = "upload" | "asr" | "summary" | "actions";
export type StageStatus =
  | "pending"
  | "running"
  | "done"
  | "failed"
  | "skipped";

export interface StageState {
  status: StageStatus;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

export interface MeetingStatus {
  meeting_id: string;
  state: MeetingState;
  stages: Partial<Record<PipelineStage, StageState>>;
  error: string | null;
  updated_at: string;
  transcription_provider: string | null;
  llm_model: string | null;
}

export interface SpeakerTurn {
  speaker: string;
  start_ms: number;
  end_ms: number;
  text: string;
}

export interface TranscriptSegment {
  id: string;
  speaker: string;
  start_ms: number;
  end_ms: number;
  text: string;
  confidence: number | null;
}

export interface Transcript {
  meeting_id: string;
  language: string | null;
  duration_ms: number | null;
  segments: TranscriptSegment[];
  speakers: string[];
  provider: string;
  generated_at: string;
}

export interface Summary {
  meeting_id: string;
  summary: string;
  decisions: string[];
  topics: string[];
  model: string;
  generated_at: string;
}

export interface ActionItem {
  id: string;
  text: string;
  owner: string | null;
  due: string | null;
  status: "open" | "done" | "dismissed";
  source_segment_ids: string[];
}

export interface ActionsBundle {
  meeting_id: string;
  items: ActionItem[];
  model: string;
  generated_at: string;
}

export interface Meeting {
  meeting_id: string;
  recording_key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  created_at: string;
  duration_ms: number | null;
  speaker_count: number | null;
  summary_excerpt: string | null;
  state: MeetingState;
  error: string | null;
}

// --- Search ---

export type HitKind = "summary" | "transcript" | "title";

export interface SearchHit {
  meeting_id: string;
  title: string;
  created_at: string;
  kind: HitKind;
  score: number;
  snippet: string;
  segment_id: string | null;
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
  meetings_searched: number;
  truncated: boolean;
}
