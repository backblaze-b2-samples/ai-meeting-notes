<!-- last_verified: 2026-05-26 -->
# Embedding-Based Search

> Status: **Deferred** — v1 search is exact substring matching.

## Goal
Replace the substring scan in `service/search.py` with an embedding-based
similarity search so queries return semantically related hits even when
the exact words don't appear in the transcript.

## Why v1 is exact-substring
Exact substring is:
- One file (`service/search.py`)
- No new index, no migration story
- Demos B2's read path under load (every query reads every summary +
  transcript) — which is the load-bearing demo

Embeddings add a stateful index layer that competes with the "B2 is the
system of record" story unless we put the index in B2 too.

## Sketch
- At pipeline-done time, compute a per-meeting embedding from the
  summary + key transcript turns. Stash it as
  `meetings/<id>/embedding.json` (the embedding becomes a fifth artifact).
- A new `repo/embeddings.py` adapter calls the embedding provider
  (OpenAI / VoyageAI / Cohere) — provider-pluggable like
  `repo/transcription.py`.
- Search: load every `embedding.json`, compute cosine similarity to the
  query embedding (also computed on demand), rank hits.
- Hot-cache the embedding vectors in-memory at API startup; falling back
  to a B2 read on a cache miss keeps the "B2 is the system of record"
  posture intact.
- Hybrid path: keep the substring scan as a co-equal scorer so exact-keyword
  queries still surface correctly.

## Rough effort
1 week for a clean v1, assuming the embedding provider is decided.
