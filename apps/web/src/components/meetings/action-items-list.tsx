"use client";

import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import type { ActionItem, ActionsBundle } from "@ai-meeting-notes/shared";

interface ActionItemsListProps {
  actions: ActionsBundle | undefined;
  loading?: boolean;
  /** Called when the user clicks a source-segment chip — typically to seek. */
  onSeekSegment?: (segmentId: string) => void;
}

/**
 * Checkbox list of action items extracted from the meeting. Checking
 * an item is purely client-side state for v1 — no PATCH endpoint yet,
 * so re-loading the page resets the checks. The exec-plan for the
 * "action-item persistence" feature is the natural follow-up.
 */
export function ActionItemsList({
  actions,
  loading,
  onSeekSegment,
}: ActionItemsListProps) {
  const [done, setDone] = useState<Set<string>>(new Set());

  if (loading && !actions) {
    return (
      <Card>
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title">Action Items</CardTitle>
        </CardHeader>
        <CardContent className="p-5 space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-5 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (!actions) return null;

  const toggle = (id: string) => {
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (actions.items.length === 0) {
    return (
      <Card>
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title">Action Items</CardTitle>
        </CardHeader>
        <CardContent className="p-5">
          <p className="text-sm text-muted-foreground">
            No action items were extracted.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">
          Action Items ({actions.items.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="p-5 space-y-3">
        {actions.items.map((item) => (
          <ActionRow
            key={item.id}
            item={item}
            done={done.has(item.id)}
            onToggle={() => toggle(item.id)}
            onSeekSegment={onSeekSegment}
          />
        ))}
      </CardContent>
    </Card>
  );
}

function ActionRow({
  item,
  done,
  onToggle,
  onSeekSegment,
}: {
  item: ActionItem;
  done: boolean;
  onToggle: () => void;
  onSeekSegment?: (segmentId: string) => void;
}) {
  return (
    <div className="flex items-start gap-3">
      <Checkbox checked={done} onCheckedChange={onToggle} aria-label={item.text} />
      <div className="flex-1 min-w-0">
        <div className={done ? "line-through text-muted-foreground" : ""}>
          <span className="text-sm">{item.text}</span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {item.owner && <span>Owner: {item.owner}</span>}
          {item.due && <span>Due: {item.due}</span>}
          {item.source_segment_ids.length > 0 && onSeekSegment && (
            <button
              type="button"
              onClick={() => onSeekSegment(item.source_segment_ids[0])}
              className="text-xs underline hover:no-underline"
            >
              Source
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
