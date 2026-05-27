<!-- last_verified: 2026-05-26 -->
# Calendar Integration (Google / Microsoft)

> Status: **Deferred** — v1 has no calendar awareness. This plan documents the path.

## Goal
Auto-attach a recording to the matching calendar event so the meeting title, attendees, and scheduled time appear alongside the transcript / summary / action items.

## Why deferred
Calendar integration pulls in:
- OAuth (Google + Microsoft), token refresh, scope management
- Per-provider quirks (recurring events, time-zone handling, attachment APIs)
- Per-user state — which event matches *this* recording?
- A consent UI that has nothing to do with B2

Cleaner to ship as a follow-up.

## Sketch
- Add a `calendar_event` field to `Meeting` (`{ provider, event_id, title, start, end, attendees }`).
- OAuth flow stored in a new `repo/calendar.py` adapter (Google + Microsoft).
- Backend matches a recording to an event by start-time window + bucket / channel name. Manual override available from the meeting detail page.
- Meeting card shows the event title and attendee chips instead of the raw filename.

## Rough effort
2-3 weeks for both providers + the consent UI.
