import type {
  ActionsBundle,
  DailyUploadCount,
  FileMetadata,
  FileUploadResponse,
  Meeting,
  MeetingStatus,
  SearchResponse,
  Summary,
  Transcript,
  UploadStats,
} from "@ai-meeting-notes/shared";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Typed API error with HTTP status code for caller-side branching. */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True for 408, 429, 500, 502, 503, 504 — worth retrying. */
  get isRetryable(): boolean {
    return [408, 429, 500, 502, 503, 504].includes(this.status);
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isConflict(): boolean {
    return this.status === 409;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError("Network error — check your connection", 0);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      body.detail || `API error: ${res.status}`,
      res.status,
    );
  }
  return res.json();
}

export async function getHealth() {
  return apiFetch<{ status: string; b2_connected: boolean }>("/health");
}

// --- Bucket explorer (kept verbatim from the starter) ---

export async function getFiles(prefix = "", limit = 100) {
  return apiFetch<FileMetadata[]>(
    `/files?prefix=${encodeURIComponent(prefix)}&limit=${limit}`
  );
}

export async function getFileStats() {
  return apiFetch<UploadStats>("/files/stats");
}

export async function getUploadActivity(days = 7) {
  return apiFetch<DailyUploadCount[]>(`/files/stats/activity?days=${days}`);
}

export async function getFile(key: string) {
  return apiFetch<FileMetadata>(`/files/${key}`);
}

export async function getDownloadUrl(key: string) {
  return apiFetch<{ url: string }>(`/files/${key}/download`);
}

export async function getPreviewUrl(key: string) {
  return apiFetch<{ url: string }>(`/files/${key}/preview`);
}

export async function deleteFile(key: string) {
  return apiFetch<{ deleted: boolean; key: string }>(`/files/${key}`, {
    method: "DELETE",
  });
}

export interface BulkDeleteError {
  Key: string;
  Code: string;
  Message: string;
}

export interface BulkDeleteResult {
  deleted: string[];
  errors: BulkDeleteError[];
}

export async function bulkDeleteFiles(keys: string[]) {
  return apiFetch<BulkDeleteResult>("/files/bulk-delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keys }),
  });
}

// --- Meetings ---

export async function listMeetings(limit = 100) {
  return apiFetch<Meeting[]>(`/meetings?limit=${limit}`);
}

export async function getMeeting(meetingId: string) {
  return apiFetch<Meeting>(`/meetings/${encodeURIComponent(meetingId)}`);
}

export async function deleteMeeting(meetingId: string) {
  return apiFetch<BulkDeleteResult>(
    `/meetings/${encodeURIComponent(meetingId)}`,
    { method: "DELETE" },
  );
}

export async function getMeetingStatus(meetingId: string) {
  return apiFetch<MeetingStatus>(
    `/meetings/${encodeURIComponent(meetingId)}/status`,
  );
}

export async function getMeetingTranscript(meetingId: string) {
  return apiFetch<Transcript>(
    `/meetings/${encodeURIComponent(meetingId)}/transcript`,
  );
}

export async function getMeetingSummary(meetingId: string) {
  return apiFetch<Summary>(
    `/meetings/${encodeURIComponent(meetingId)}/summary`,
  );
}

export async function getMeetingActions(meetingId: string) {
  return apiFetch<ActionsBundle>(
    `/meetings/${encodeURIComponent(meetingId)}/actions`,
  );
}

export async function getMeetingPlaybackUrl(meetingId: string) {
  return apiFetch<{ url: string; expires_in: number }>(
    `/meetings/${encodeURIComponent(meetingId)}/playback`,
  );
}

export async function getMeetingDownloadUrl(meetingId: string) {
  return apiFetch<{ url: string; expires_in: number }>(
    `/meetings/${encodeURIComponent(meetingId)}/download`,
  );
}

// --- Search ---

export async function searchMeetings(query: string) {
  return apiFetch<SearchResponse>(`/search?q=${encodeURIComponent(query)}`);
}

// --- Upload ---

/**
 * Upload a recording. Defaults to `/meetings` (the meeting-pipeline
 * entry point); pass `/upload` to hit the legacy alias.
 */
export function uploadFile(
  file: File,
  onProgress?: (percent: number) => void,
  endpoint: "/meetings" | "/upload" = "/meetings",
): Promise<Meeting | FileUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          reject(new ApiError(body.detail || `Upload failed: ${xhr.status}`, xhr.status));
        } catch {
          reject(new ApiError(`Upload failed: ${xhr.status}`, xhr.status));
        }
      }
    });

    xhr.addEventListener("error", () =>
      reject(new ApiError("Network error — check your connection", 0)),
    );
    xhr.addEventListener("abort", () =>
      reject(new ApiError("Upload aborted", 0)),
    );

    xhr.open("POST", `${API_BASE}${endpoint}`);
    xhr.send(formData);
  });
}
