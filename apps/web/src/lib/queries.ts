"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  bulkDeleteFiles,
  deleteFile,
  deleteMeeting,
  getFiles,
  getFileStats,
  getMeeting,
  getMeetingActions,
  getMeetingStatus,
  getMeetingSummary,
  getMeetingTranscript,
  getPreviewUrl,
  getUploadActivity,
  listMeetings,
  searchMeetings,
} from "@/lib/api-client";
import type {
  ActionsBundle,
  FileMetadata,
  Meeting,
  MeetingStatus,
  SearchResponse,
  Summary,
  Transcript,
} from "@ai-meeting-notes/shared";

// Single source of truth for query keys. Keep them tightly scoped so that
// invalidating one slice doesn't blow away unrelated caches.
export const qk = {
  all: ["b2"] as const,
  files: (prefix?: string, limit?: number) =>
    [...qk.all, "files", prefix ?? "", limit ?? 100] as const,
  stats: () => [...qk.all, "stats"] as const,
  uploadActivity: (days: number) =>
    [...qk.all, "stats", "activity", days] as const,
  preview: (key: string) => [...qk.all, "preview", key] as const,
  // Meetings
  meetings: (limit?: number) => [...qk.all, "meetings", limit ?? 100] as const,
  meeting: (id: string) => [...qk.all, "meetings", "one", id] as const,
  meetingStatus: (id: string) =>
    [...qk.all, "meetings", "one", id, "status"] as const,
  transcript: (id: string) =>
    [...qk.all, "meetings", "one", id, "transcript"] as const,
  summary: (id: string) => [...qk.all, "meetings", "one", id, "summary"] as const,
  actions: (id: string) => [...qk.all, "meetings", "one", id, "actions"] as const,
  search: (q: string) => [...qk.all, "search", q] as const,
};

// --- Files (explorer) ---

export function useFiles(prefix = "", limit = 100) {
  return useQuery<FileMetadata[], ApiError>({
    queryKey: qk.files(prefix, limit),
    queryFn: () => getFiles(prefix, limit),
  });
}

export function useFileStats() {
  return useQuery({
    queryKey: qk.stats(),
    queryFn: getFileStats,
  });
}

export function useUploadActivity(days = 7) {
  return useQuery({
    queryKey: qk.uploadActivity(days),
    queryFn: () => getUploadActivity(days),
  });
}

export function usePreviewUrl(key: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: qk.preview(key ?? ""),
    queryFn: () => getPreviewUrl(key as string),
    enabled: enabled && !!key,
    staleTime: 60_000,
  });
}

export function useDeleteFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fileKey: string) => deleteFile(fileKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.all });
    },
  });
}

export function useBulkDeleteFiles() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (keys: string[]) => bulkDeleteFiles(keys),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.all });
    },
  });
}

// --- Meetings ---

const TERMINAL_STATES = new Set(["done", "failed"]);

export function useMeetings(limit = 100) {
  return useQuery<Meeting[], ApiError>({
    queryKey: qk.meetings(limit),
    queryFn: () => listMeetings(limit),
  });
}

export function useMeeting(meetingId: string | undefined) {
  return useQuery<Meeting, ApiError>({
    queryKey: qk.meeting(meetingId ?? ""),
    queryFn: () => getMeeting(meetingId as string),
    enabled: !!meetingId,
  });
}

/**
 * Poll `status.json` until the pipeline reaches a terminal state.
 * Returns the parsed status payload; the UI uses it to drive the stage
 * indicator and to invalidate transcript/summary/actions queries when
 * the state transitions to `done`.
 */
export function useMeetingStatus(
  meetingId: string | undefined,
  pollIntervalMs = 2_500,
) {
  return useQuery<MeetingStatus, ApiError>({
    queryKey: qk.meetingStatus(meetingId ?? ""),
    queryFn: () => getMeetingStatus(meetingId as string),
    enabled: !!meetingId,
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      if (!state || TERMINAL_STATES.has(state)) return false;
      return pollIntervalMs;
    },
  });
}

export function useMeetingTranscript(
  meetingId: string | undefined,
  enabled = true,
) {
  return useQuery<Transcript, ApiError>({
    queryKey: qk.transcript(meetingId ?? ""),
    queryFn: () => getMeetingTranscript(meetingId as string),
    enabled: !!meetingId && enabled,
  });
}

export function useMeetingSummary(
  meetingId: string | undefined,
  enabled = true,
) {
  return useQuery<Summary, ApiError>({
    queryKey: qk.summary(meetingId ?? ""),
    queryFn: () => getMeetingSummary(meetingId as string),
    enabled: !!meetingId && enabled,
  });
}

export function useMeetingActions(
  meetingId: string | undefined,
  enabled = true,
) {
  return useQuery<ActionsBundle, ApiError>({
    queryKey: qk.actions(meetingId ?? ""),
    queryFn: () => getMeetingActions(meetingId as string),
    enabled: !!meetingId && enabled,
  });
}

export function useDeleteMeeting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (meetingId: string) => deleteMeeting(meetingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.all });
    },
  });
}

// --- Search ---

export function useSearch(query: string, enabled = true) {
  return useQuery<SearchResponse, ApiError>({
    queryKey: qk.search(query),
    queryFn: () => searchMeetings(query),
    enabled: enabled && query.trim().length > 0,
    staleTime: 30_000,
  });
}
