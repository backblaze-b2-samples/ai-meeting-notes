"use client";

import { useMemo } from "react";

import type { Transcript } from "@ai-meeting-notes/shared";
import { formatDuration } from "@/lib/utils";

interface TranscriptViewProps {
  transcript: Transcript | undefined;
  /** Current playback time in ms; used to highlight the active segment. */
  currentTimeMs: number;
  /** Called when a segment is clicked — typically to seek the player. */
  onSeek?: (timeMs: number) => void;
}

/**
 * Speaker-turn list with click-to-seek + current-segment highlight.
 *
 * Segments are rendered linearly; we group adjacent segments with the
 * same speaker into a "turn" to keep the visual scan short. The active
 * segment is the one whose [start, end) brackets `currentTimeMs`.
 */
export function TranscriptView({
  transcript,
  currentTimeMs,
  onSeek,
}: TranscriptViewProps) {
  const turns = useMemo(() => {
    const segments = transcript?.segments ?? [];
    if (segments.length === 0) return [];

    const grouped: Array<{
      speaker: string;
      start_ms: number;
      end_ms: number;
      segmentIds: string[];
      lines: { id: string; start_ms: number; end_ms: number; text: string }[];
    }> = [];
    for (const seg of segments) {
      const last = grouped[grouped.length - 1];
      if (last && last.speaker === seg.speaker) {
        last.end_ms = seg.end_ms;
        last.segmentIds.push(seg.id);
        last.lines.push({
          id: seg.id,
          start_ms: seg.start_ms,
          end_ms: seg.end_ms,
          text: seg.text,
        });
      } else {
        grouped.push({
          speaker: seg.speaker,
          start_ms: seg.start_ms,
          end_ms: seg.end_ms,
          segmentIds: [seg.id],
          lines: [
            {
              id: seg.id,
              start_ms: seg.start_ms,
              end_ms: seg.end_ms,
              text: seg.text,
            },
          ],
        });
      }
    }
    return grouped;
  }, [transcript]);

  if (!transcript || turns.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No transcript available.</p>
    );
  }

  return (
    <ol className="space-y-4">
      {turns.map((turn, i) => (
        <li key={`${turn.start_ms}-${i}`} className="grid grid-cols-[120px_1fr] gap-3">
          <div className="text-xs text-muted-foreground tabular-nums">
            <div className="font-semibold text-foreground">{turn.speaker}</div>
            <button
              type="button"
              className="font-mono hover:underline"
              onClick={() => onSeek?.(turn.start_ms)}
              aria-label={`Jump to ${formatDuration(turn.start_ms)}`}
            >
              {formatDuration(turn.start_ms)}
            </button>
          </div>
          <div className="space-y-1 text-sm">
            {turn.lines.map((line) => {
              const isActive =
                currentTimeMs >= line.start_ms && currentTimeMs < line.end_ms;
              return (
                <button
                  type="button"
                  key={line.id}
                  onClick={() => onSeek?.(line.start_ms)}
                  className={`block w-full text-left rounded-sm px-1 py-0.5 transition-colors ${
                    isActive
                      ? "bg-[var(--accent-subtle)] font-medium"
                      : "hover:bg-muted/50"
                  }`}
                >
                  {line.text}
                </button>
              );
            })}
          </div>
        </li>
      ))}
    </ol>
  );
}
