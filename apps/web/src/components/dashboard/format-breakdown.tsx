"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useFileStats } from "@/lib/queries";

const STATE_LABELS: Record<string, string> = {
  queued: "Queued",
  transcribing: "Transcribing",
  summarizing: "Summarizing",
  done: "Done",
  failed: "Failed",
};

/**
 * Pipeline-state breakdown for the dashboard. Shows how many meetings
 * are sitting in each pipeline state so you can spot stuck pipelines
 * at a glance.
 *
 * Returns `null` when no meetings exist yet — we don't want to render
 * an empty card on first load. Consumes the same `useFileStats()` query
 * as `StatsCards`; TanStack Query dedupes on the shared `qk.stats()` key.
 */
export function FormatBreakdown() {
  const { data: stats } = useFileStats();
  const states = stats?.meetings_by_state ?? {};
  const entries = Object.entries(states).sort((a, b) => b[1] - a[1]);

  if (entries.length === 0) {
    return null;
  }

  return (
    <Card className="card-hover">
      <CardHeader className="flex flex-row items-center justify-between pt-4 pb-2 px-4 space-y-0">
        <CardTitle className="text-xs font-semibold text-muted-foreground">
          Pipeline State
        </CardTitle>
      </CardHeader>
      <CardContent className="pb-4 px-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          {entries.map(([state, count], i) => (
            <span key={state} className="flex items-center gap-3">
              <span>
                <span className="font-medium">
                  {STATE_LABELS[state] ?? state}
                </span>{" "}
                <span className="text-muted-foreground">{count}</span>
              </span>
              {i < entries.length - 1 && (
                <span className="text-muted-foreground/50" aria-hidden>
                  ·
                </span>
              )}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
