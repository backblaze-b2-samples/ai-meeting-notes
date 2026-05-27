"use client";

import { use, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Download } from "lucide-react";
import { toast } from "sonner";

import { ActionItemsList } from "@/components/meetings/action-items-list";
import { PipelineStatus } from "@/components/meetings/pipeline-status";
import { SummaryPanel } from "@/components/meetings/summary-panel";
import { TranscriptView } from "@/components/meetings/transcript-view";
import { Waveform } from "@/components/meetings/waveform";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ApiError,
  getMeetingDownloadUrl,
  getMeetingPlaybackUrl,
} from "@/lib/api-client";
import {
  useMeeting,
  useMeetingActions,
  useMeetingStatus,
  useMeetingSummary,
  useMeetingTranscript,
} from "@/lib/queries";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function MeetingDetailPage({ params }: PageProps) {
  const { id } = use(params);

  const meeting = useMeeting(id);
  const status = useMeetingStatus(id);
  const transcript = useMeetingTranscript(id, status.data?.state !== "queued");
  const summary = useMeetingSummary(
    id,
    status.data?.state === "summarizing" || status.data?.state === "done",
  );
  const actions = useMeetingActions(id, status.data?.state === "done");

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [audioSrc, setAudioSrc] = useState<string | null>(null);
  const [currentTimeMs, setCurrentTimeMs] = useState(0);

  // Lazy-load the inline player on first visit. The presigned URL is
  // short-lived (10 min) — if the user keeps the page open longer,
  // the next play will refresh via the same fetch.
  useEffect(() => {
    let cancelled = false;
    if (!id) return;
    getMeetingPlaybackUrl(id)
      .then(({ url }) => {
        if (!cancelled) setAudioSrc(url);
      })
      .catch((err: unknown) => {
        // 404 here just means the recording isn't ready yet — not an error
        if (err instanceof ApiError && err.isNotFound) return;
        const msg =
          err instanceof Error ? err.message : "Failed to load playback URL";
        toast.error(msg);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (meeting.error && meeting.error.status === 404) {
    notFound();
  }

  const handleSeek = (timeMs: number) => {
    const el = audioRef.current;
    if (!el) return;
    el.currentTime = timeMs / 1000;
    void el.play().catch(() => {
      // Autoplay may be blocked; users can click play manually.
    });
  };

  const handleSeekSegment = (segmentId: string) => {
    const segment = transcript.data?.segments.find((s) => s.id === segmentId);
    if (segment) handleSeek(segment.start_ms);
  };

  const handleDownload = async () => {
    try {
      const { url } = await getMeetingDownloadUrl(id);
      window.open(url, "_blank");
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Failed to get download URL";
      toast.error(msg);
    }
  };

  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <Link
            href="/meetings"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-3 w-3" /> All meetings
          </Link>
          {meeting.isLoading ? (
            <Skeleton className="mt-2 h-6 w-64" />
          ) : (
            <h1 className="page-title mt-1.5 truncate">
              {meeting.data?.filename ?? id}
            </h1>
          )}
        </div>
        <Button size="sm" variant="outline" className="h-8" onClick={handleDownload}>
          <Download className="h-3.5 w-3.5" />
          Download recording
        </Button>
      </div>

      <PipelineStatus status={status.data} />

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Recording &amp; Transcript</CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            {audioSrc ? (
              <div className="space-y-2">
                <audio
                  controls
                  ref={audioRef}
                  src={audioSrc}
                  className="w-full"
                  onTimeUpdate={(e) =>
                    setCurrentTimeMs(
                      Math.round((e.target as HTMLAudioElement).currentTime * 1000),
                    )
                  }
                />
                <Waveform
                  durationMs={meeting.data?.duration_ms ?? null}
                  className="h-10 w-full text-primary/60"
                />
              </div>
            ) : (
              <Skeleton className="h-12 w-full" />
            )}

            {transcript.error ? (
              <ErrorState error={transcript.error} onRetry={() => transcript.refetch()} />
            ) : transcript.isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-4 w-full" />
                ))}
              </div>
            ) : (
              <TranscriptView
                transcript={transcript.data}
                currentTimeMs={currentTimeMs}
                onSeek={handleSeek}
              />
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <SummaryPanel
            summary={summary.data}
            loading={status.data?.state !== "done" && summary.isLoading}
          />
          <ActionItemsList
            actions={actions.data}
            loading={status.data?.state !== "done" && actions.isLoading}
            onSeekSegment={handleSeekSegment}
          />
        </div>
      </div>
    </div>
  );
}
