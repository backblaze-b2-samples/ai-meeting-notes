"use client";

import Link from "next/link";
import { Mic, RefreshCw, Upload } from "lucide-react";

import { MeetingCard } from "@/components/meetings/meeting-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useMeetings } from "@/lib/queries";

export default function MeetingsPage() {
  const { data: meetings = [], isLoading, isFetching, error, refetch } =
    useMeetings();

  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Meetings</h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            Every meeting you have stored in B2 — open one to see the
            transcript, summary, and action items.
          </p>
        </div>
        <Button asChild size="sm" className="h-8">
          <Link href="/upload">
            <Upload className="h-3.5 w-3.5" />
            Upload recording
          </Link>
        </Button>
      </div>
      <div className="animate-fade-in-up stagger-2">
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-40 w-full" />
            ))}
          </div>
        ) : error ? (
          <Card>
            <CardContent className="p-0">
              <ErrorState error={error} onRetry={() => refetch()} />
            </CardContent>
          </Card>
        ) : meetings.length === 0 ? (
          <Card>
            <CardContent className="p-0">
              <EmptyState
                icon={Mic}
                title="No meetings yet"
                description="Upload a recording to kick off transcription and summarization."
              />
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                {meetings.length} {meetings.length === 1 ? "meeting" : "meetings"}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                disabled={isFetching}
                className="h-7 text-xs"
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 mr-1 ${isFetching ? "animate-spin" : ""}`}
                />
                Refresh
              </Button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {meetings.map((m) => (
                <MeetingCard key={m.meeting_id} meeting={m} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
