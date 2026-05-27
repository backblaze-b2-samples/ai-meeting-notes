"use client";

import Link from "next/link";
import { Mic, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { FormatBreakdown } from "@/components/dashboard/format-breakdown";
import { RecentUploadsTable } from "@/components/dashboard/recent-uploads-table";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { UploadChart } from "@/components/dashboard/upload-chart";
import { useFileStats } from "@/lib/queries";

/**
 * Dashboard body. Splits into two layouts driven by `useFileStats()`:
 *
 *  - **Empty bucket** (`total_meetings === 0`, not loading/erroring):
 *    a single hero card prompting the first upload. We deliberately keep
 *    `StatsCards`/charts/table off-screen here — they're all-zero on an
 *    empty bucket and dilute the call to action.
 *  - **Populated**: the usual StatsCards + FormatBreakdown + chart/table grid.
 */
export function DashboardView() {
  const { data: stats, isLoading, error } = useFileStats();
  const isEmpty =
    !isLoading && !error && (stats?.total_meetings ?? 0) === 0;

  if (isEmpty) {
    return (
      <Card className="animate-fade-in-up">
        <CardContent className="p-0">
          <EmptyState
            icon={Mic}
            title="No meetings yet — upload your first recording"
            description="Drop an mp3, wav, m4a, or mp4 to kick off transcription, summary, and action-item extraction."
            action={
              <Button asChild size="sm" className="h-8">
                <Link href="/upload">
                  <Upload className="h-3.5 w-3.5" />
                  Upload recording
                </Link>
              </Button>
            }
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <StatsCards />
      <FormatBreakdown />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="animate-fade-in-up stagger-3">
          <UploadChart />
        </div>
        <div className="animate-fade-in-up stagger-4">
          <RecentUploadsTable />
        </div>
      </div>
    </>
  );
}
