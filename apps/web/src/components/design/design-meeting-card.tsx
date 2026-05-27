"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MeetingCard } from "@/components/meetings/meeting-card";
import { Section } from "./section";
import type { Meeting } from "@ai-meeting-notes/shared";

// Static demo meeting — keys, sizes, timestamps are fabricated. Delete
// will toast a failure when clicked since the meeting doesn't resolve
// in B2; that's the intended showcase behavior.
const sampleMeeting: Meeting = {
  meeting_id: "demo000000000001",
  recording_key: "meetings/demo000000000001/recording.mp3",
  filename: "recording.mp3",
  size_bytes: 287_440,
  size_human: "280.7 KB",
  content_type: "audio/mpeg",
  created_at: "2026-05-20T14:23:00.000Z",
  duration_ms: 1_842_000,
  speaker_count: 3,
  summary_excerpt:
    "Quarterly planning sync. Decided to ship the new onboarding flow next week and bring in a designer for the visual refresh.",
  state: "done",
  error: null,
};

export function DesignMeetingCard() {
  return (
    <Section
      id="meeting-card"
      title="Meeting Card"
      description="The default Meetings primitive on this kit. Renders the recording filename, pipeline state badge, summary excerpt, and the Open / Delete actions."
    >
      <Card>
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title">Sample meeting</CardTitle>
        </CardHeader>
        <CardContent className="p-5">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <MeetingCard meeting={sampleMeeting} />
          </div>
          <p className="text-xs text-muted-foreground mt-4">
            Source: <code className="font-mono">apps/web/src/components/meetings/meeting-card.tsx</code> ·
            also documented in <code className="font-mono">docs/features/meetings-library.md</code>.
          </p>
        </CardContent>
      </Card>
    </Section>
  );
}
