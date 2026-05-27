"use client";

import Link from "next/link";
import { ArrowRight, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api-client";
import { useDeleteMeeting } from "@/lib/queries";
import { formatDate } from "@/lib/utils";
import type { Meeting } from "@ai-meeting-notes/shared";

const STATE_BADGE: Record<Meeting["state"], { label: string; tone: string }> = {
  queued: { label: "Queued", tone: "bg-muted text-foreground" },
  transcribing: {
    label: "Transcribing",
    tone: "bg-[var(--accent-subtle)] text-foreground",
  },
  summarizing: {
    label: "Summarizing",
    tone: "bg-[var(--accent-subtle)] text-foreground",
  },
  done: { label: "Done", tone: "bg-primary/10 text-primary" },
  failed: { label: "Failed", tone: "bg-destructive/10 text-destructive" },
};

interface MeetingCardProps {
  meeting: Meeting;
}

/**
 * Card primitive for the Meetings grid. Surfaces title, date, pipeline
 * state, and a one-line summary excerpt when the LLM stage has
 * completed. The whole card is link-blocked to the detail page.
 */
export function MeetingCard({ meeting }: MeetingCardProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const deleteMutation = useDeleteMeeting();
  const badge = STATE_BADGE[meeting.state] ?? STATE_BADGE.queued;

  const handleDelete = () => {
    deleteMutation.mutate(meeting.meeting_id, {
      onSuccess: () => {
        toast.success("Meeting deleted");
        setConfirmDelete(false);
      },
      onError: (err) => {
        const detail = err instanceof ApiError ? err.message : "Failed to delete";
        toast.error(detail);
      },
    });
  };

  return (
    <>
      <Card className="card-hover">
        <CardContent className="space-y-3 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <Link
                href={`/meetings/${meeting.meeting_id}`}
                className="text-sm font-semibold hover:underline line-clamp-2"
              >
                {meeting.filename}
              </Link>
              <p className="mt-1 text-xs text-muted-foreground">
                {formatDate(meeting.created_at)} · {meeting.size_human}
              </p>
            </div>
            <span
              className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full whitespace-nowrap ${badge.tone}`}
            >
              {badge.label}
            </span>
          </div>

          {meeting.summary_excerpt ? (
            <p className="text-xs text-muted-foreground line-clamp-3">
              {meeting.summary_excerpt}
            </p>
          ) : meeting.state === "failed" && meeting.error ? (
            <p className="text-xs text-destructive line-clamp-3">
              {meeting.error}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground italic">
              Summary not available yet.
            </p>
          )}

          <div className="flex items-center justify-between">
            <Button asChild size="sm" variant="outline" className="h-7 text-xs">
              <Link href={`/meetings/${meeting.meeting_id}`}>
                Open
                <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setConfirmDelete(true)}
              className="text-destructive h-7"
              aria-label="Delete meeting"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this meeting?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the recording, transcript, summary, and
              action items from B2. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
