<!-- last_verified: 2026-05-26 -->
# Feature: Bucket Explorer (Files)

## Purpose
List, preview, download, and delete **everything** stored in Backblaze B2 — including the per-meeting bundles under `meetings/<id>/`, generic uploads under `uploads/`, and anything else in the bucket. This is the ops-style explorer; the primary meeting UX lives at `/meetings`.

## Used By
- UI: `/files` page, file browser component
- API: `GET /files`, `GET /files/{key}`, `GET /files/{key}/download`, `GET /files/{key}/preview`, `DELETE /files/{key}`, `POST /files/bulk-delete`

## Core Functions
- `apps/web/src/components/files/file-browser.tsx` — tree view with per-row and per-folder (indeterminate-aware) checkboxes, expand/collapse folders, type-specific icons, hover action menus, header action bar with "N selected" / Clear / Delete, bulk-delete confirm dialog
- `apps/web/src/components/files/file-preview.tsx` — dialog modal for file preview
- `apps/web/src/components/files/file-metadata-panel.tsx` — structured metadata display
- `apps/web/src/lib/file-tree.ts` — `buildFileTree()` converts flat S3 keys to folder/file hierarchy
- `apps/web/src/lib/api-client.ts` — `getFiles()`, `getDownloadUrl()`, `deleteFile()`, `bulkDeleteFiles()`
- `apps/web/src/lib/queries.ts` — `useFiles()`, `useDeleteFile()`, `useBulkDeleteFiles()`
- `services/api/app/runtime/files.py` — HTTP handlers
- `services/api/app/service/files.py` — business logic, key validation, bulk delete orchestration
- `services/api/app/repo/b2_client.py` — `list_files()`, `get_file_metadata()`, `get_presigned_url()`, `delete_file()`, `delete_files_batch()`

## Canonical Files
- File route handlers: `services/api/app/runtime/files.py`
- File tree builder: `apps/web/src/lib/file-tree.ts`
- B2 data access pattern: `services/api/app/repo/b2_client.py`

## Inputs
- prefix: string (optional filter for file listing)
- limit: int (max files to return, 1-1000, default 100)
- key: string (file key for get/download/delete — no path traversal)
- `POST /files/bulk-delete` body: `{ keys: string[] }` (1-1000 keys; each key validated against the same path-traversal rules as the single-delete endpoint)

## Outputs
- `GET /files` -> `FileMetadata[]` (sorted most recent first)
- `GET /files/{key}` -> `FileMetadata`
- `GET /files/{key}/download` -> `{ url }` (attachment, 10-min expiry; bumps the `total_downloads` counter)
- `GET /files/{key}/preview` -> `{ url }` (inline rendering, 10-min expiry; does NOT increment the counter)
- `DELETE /files/{key}` -> `{ deleted: true, key }`
- `POST /files/bulk-delete` -> `{ deleted: string[], errors: { Key, Code, Message }[] }` — partial success is allowed and surfaced to the UI

## Flow
- Page loads -> fetches file list from `GET /files` (sorted most recent first)
- Files organized into tree view — folders expand/collapse, files shown with type-specific icons (audio rows show the `FileAudioIcon`)
- Top-level folders auto-expand on load — so `meetings/` and `uploads/` are immediately visible
- User hovers file row -> action buttons appear (preview / download / delete)
- Per-row checkbox selects a single file; per-folder checkbox toggles every descendant file (indeterminate when partial). Header shows "N selected" with Clear and Delete actions.
- Preview: opens dialog, fetches a preview-only presigned URL via `/files/{key}/preview` and renders image/PDF inline
- Download: fetches presigned URL via `/files/{key}/download`, opens in new tab, bumps the download counter, triggers a stats refresh
- Delete: calls `DELETE /files/{key}`, removes row from tree, shows toast
- Bulk delete: confirm dialog -> `POST /files/bulk-delete` with the selected keys -> toast reports full / partial / total failure
- All key-based API calls validated against path-traversal patterns; bulk-delete validates every key before any B2 call so a single bad payload doesn't partially mutate the bucket.

## Meetings vs. Files
The Files explorer is intentionally the full-bucket view. Per-meeting bundles under `meetings/<id>/` are *also* deletable from here — that's a power-user surface, useful for surgical cleanup. The primary meeting UX (state badges, summary, playback) lives at `/meetings`. To wipe a whole meeting in one call, use `DELETE /meetings/<id>` rather than deleting each bundle file by hand from this page.

## Edge Cases
- File not found (deleted externally) -> API returns 404
- Invalid file key (traversal attempt, empty key) -> API returns 400
- B2 unreachable -> API error, toast notification
- Empty bucket -> "This bucket is empty" message with upload prompt
- Delete failure -> API returns 500, toast error

## UX States
- Empty: centered message with upload prompt
- Loading: skeleton rows
- Error: toast notification
- Loaded: tree view with expand/collapse folders and hover action menus

## Verification
- Test files: see `services/api/tests/test_structure.py` for boundary tests
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`

## Related Docs
- [Meetings Library](meetings-library.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [App Workflows](../app-workflows.md)
