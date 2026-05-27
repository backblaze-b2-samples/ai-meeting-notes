"use client";

import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import type { MeetingStatus, StageStatus } from "@ai-meeting-notes/shared";

interface PipelineStatusProps {
  status: MeetingStatus | undefined;
}

const STAGES: Array<{ key: "asr" | "summary" | "actions"; label: string }> = [
  { key: "asr", label: "Transcribing" },
  { key: "summary", label: "Summarizing" },
  { key: "actions", label: "Extracting actions" },
];

function StageIcon({ state }: { state: StageStatus }) {
  if (state === "done") {
    return <CheckCircle2 className="h-4 w-4 text-primary" aria-label="Done" />;
  }
  if (state === "running") {
    return (
      <Loader2
        className="h-4 w-4 animate-spin text-primary"
        aria-label="In progress"
      />
    );
  }
  if (state === "failed") {
    return <XCircle className="h-4 w-4 text-destructive" aria-label="Failed" />;
  }
  return <Circle className="h-4 w-4 text-muted-foreground" aria-label="Pending" />;
}

/**
 * Compact pipeline stage indicator. Reads `status.json` (polled via
 * TanStack Query) and renders one icon + label per stage. The whole
 * card hides itself once the pipeline reaches a terminal state — the
 * detail page surfaces the artifacts directly at that point and the
 * status strip becomes redundant.
 */
export function PipelineStatus({ status }: PipelineStatusProps) {
  if (!status) return null;

  if (status.state === "done") {
    return null;
  }

  return (
    <div className="rounded-md border border-border bg-muted/30 px-4 py-3 text-sm">
      <div className="flex items-center justify-between">
        <div className="font-semibold">
          {status.state === "failed"
            ? "Pipeline failed"
            : "Pipeline running"}
        </div>
        <div className="text-xs text-muted-foreground capitalize">
          {status.state}
        </div>
      </div>
      <ul className="mt-3 space-y-1.5">
        {STAGES.map(({ key, label }) => {
          const stage = status.stages?.[key];
          const stageStatus: StageStatus = stage?.status ?? "pending";
          return (
            <li key={key} className="flex items-center gap-2 text-xs">
              <StageIcon state={stageStatus} />
              <span className={stageStatus === "done" ? "" : "text-muted-foreground"}>
                {label}
              </span>
              {stage?.error && (
                <span className="ml-auto text-destructive">{stage.error}</span>
              )}
            </li>
          );
        })}
      </ul>
      {status.error && (
        <p className="mt-3 text-xs text-destructive">{status.error}</p>
      )}
    </div>
  );
}
