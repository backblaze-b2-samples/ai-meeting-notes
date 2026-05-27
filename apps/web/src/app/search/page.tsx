"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Search as SearchIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useSearch } from "@/lib/queries";

export default function SearchPage() {
  const [draft, setDraft] = useState("");
  const [submitted, setSubmitted] = useState("");
  const { data, isFetching, error, refetch } = useSearch(submitted, !!submitted);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(draft.trim());
  };

  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Search</h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Search every meeting&apos;s summary and transcript. Each query reads
          straight from B2 — no application database, no index.
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex items-center gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Search meetings…"
          className="max-w-md"
          aria-label="Search query"
        />
        <Button type="submit" size="sm" className="h-9">
          <SearchIcon className="h-3.5 w-3.5" />
          Search
        </Button>
      </form>

      {!submitted ? (
        <Card>
          <CardContent className="p-0">
            <EmptyState
              icon={SearchIcon}
              title="Type a query to search your meetings"
              description="Matches across every meeting's summary and transcript stored in B2."
            />
          </CardContent>
        </Card>
      ) : error ? (
        <Card>
          <CardContent className="p-0">
            <ErrorState error={error} onRetry={() => refetch()} />
          </CardContent>
        </Card>
      ) : isFetching ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : !data || data.hits.length === 0 ? (
        <Card>
          <CardContent className="p-0">
            <EmptyState
              icon={SearchIcon}
              title={`No results for "${submitted}"`}
              description={`Searched ${data?.meetings_searched ?? 0} meetings.`}
            />
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            {data.hits.length} {data.hits.length === 1 ? "hit" : "hits"} across{" "}
            {data.meetings_searched}{" "}
            {data.meetings_searched === 1 ? "meeting" : "meetings"}
            {data.truncated ? " (truncated)" : ""}
          </p>
          <ul className="space-y-3">
            {data.hits.map((hit, i) => (
              <li
                key={`${hit.meeting_id}-${i}`}
                className="border border-border rounded-md p-4 hover:bg-muted/40"
              >
                <div className="flex items-start justify-between gap-3">
                  <Link
                    href={`/meetings/${hit.meeting_id}`}
                    className="text-sm font-semibold hover:underline"
                  >
                    {hit.title}
                  </Link>
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
                    {hit.kind}
                  </span>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">{hit.snippet}</p>
                <Link
                  href={`/meetings/${hit.meeting_id}`}
                  className="inline-flex items-center gap-1 mt-2 text-xs font-medium hover:underline"
                >
                  Open meeting <ArrowRight className="h-3 w-3" />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
