"use client";

import { CheckSquare, Clock, Mic, Upload } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useFileStats } from "@/lib/queries";
import { formatDuration } from "@/lib/utils";

/**
 * Meeting-centric dashboard tiles. We deliberately surface the
 * pipeline-relevant numbers (count of meetings, total transcribed
 * minutes, open action items, uploads today) instead of generic
 * storage stats — those still live one tile away on the FormatBreakdown
 * and Files page.
 */
export function StatsCards() {
  const { data: stats, isLoading, error, refetch } = useFileStats();

  if (error) {
    return (
      <Card>
        <CardContent className="p-0">
          <ErrorState error={error} onRetry={() => refetch()} />
        </CardContent>
      </Card>
    );
  }

  const cards = [
    {
      title: "Meetings",
      value: stats?.total_meetings ?? 0,
      icon: Mic,
    },
    {
      title: "Transcribed Time",
      value: formatDuration(stats?.total_duration_ms ?? 0),
      icon: Clock,
    },
    {
      title: "Open Action Items",
      value: stats?.open_action_items ?? 0,
      icon: CheckSquare,
    },
    {
      title: "Uploads Today",
      value: stats?.uploads_today ?? 0,
      icon: Upload,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card, i) => (
        <Card
          key={card.title}
          className={`card-hover animate-fade-in-up stagger-${i + 1}`}
        >
          <CardHeader className="flex flex-row items-center justify-between pt-4 pb-2 px-4 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground">
              {card.title}
            </CardTitle>
            <div className="stat-icon-wrap">
              <card.icon className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent className="pb-5 px-4">
            {isLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="stat-value">{card.value}</div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
