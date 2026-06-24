<!-- last_verified: 2026-06-24 -->
# B2 Standards Cleanup

## Issue

GitHub issue: https://github.com/backblaze-b2-samples/ai-meeting-notes/issues/2

The sample must pass the mandatory B2 standards check:

- S3-compatible API remains the default B2 surface.
- Every direct S3 client has a sample-suite user agent.
- Environment variables use the standardized `B2_*` names:
  `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`,
  `B2_REGION`, and `B2_PUBLIC_URL_BASE`.

## Completed

- Replaced legacy B2 credential, endpoint, and public URL variable names.
- Derived the S3 endpoint from `B2_REGION`.
- Updated the boto3 user agent to include the Backblaze sample-suite marker.
- Updated setup, deployment, security, and architecture docs.
- Added settings coverage for the standardized names and user-agent marker.

## Validation

- `pnpm lint`
- `pnpm lint:api`
- `pnpm test:api`
- `pnpm check:structure`
