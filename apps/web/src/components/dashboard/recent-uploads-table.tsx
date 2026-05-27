"use client";

import Link from "next/link";
import { ArrowRight, Inbox } from "lucide-react";

import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useMeetings } from "@/lib/queries";
import { formatDate } from "@/lib/utils";
import type { Meeting } from "@ai-meeting-notes/shared";

const STATE_LABEL: Record<Meeting["state"], string> = {
  queued: "Queued",
  transcribing: "Transcribing",
  summarizing: "Summarizing",
  done: "Done",
  failed: "Failed",
};

/**
 * Recent meetings table for the dashboard. Each row deep-links into the
 * meeting detail page where the synced player + transcript + summary +
 * action items live.
 */
export function RecentUploadsTable() {
  const { data: meetings = [], isLoading, error, refetch } = useMeetings(10);

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Recent Meetings</CardTitle>
        <CardAction className="self-center">
          <Link
            href="/meetings"
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            View all
            <ArrowRight className="h-3 w-3" />
          </Link>
        </CardAction>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : meetings.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="No meetings yet"
            description="Upload a recording to get started."
          />
        ) : (
          <Table className="table-fixed">
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableHead className="w-[48%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Meeting
                </TableHead>
                <TableHead className="w-[18%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  State
                </TableHead>
                <TableHead className="w-[22%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Date
                </TableHead>
                <TableHead className="w-[12%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <span className="sr-only">Open</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {meetings.map((meeting) => (
                <TableRow key={meeting.meeting_id} className="table-row-hover">
                  <TableCell className="font-medium">
                    <div className="truncate">{meeting.filename}</div>
                  </TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap text-xs">
                    {STATE_LABEL[meeting.state] ?? meeting.state}
                  </TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap">
                    {formatDate(meeting.created_at)}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    <Link
                      href={`/meetings/${meeting.meeting_id}`}
                      className="inline-flex items-center gap-1 text-xs font-medium hover:underline"
                    >
                      Open
                      <ArrowRight className="h-3 w-3" />
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
