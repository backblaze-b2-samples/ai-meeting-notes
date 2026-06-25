# Issue 2: B2 Standards

## Goal

Make the sample pass the mandatory B2 standards for issue #2:

- S3-compatible API remains the only B2 integration path.
- Every S3 client advertises the sample and Backblaze sample-suite user agent.
- B2 environment variables use the standardized names:
  `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`,
  `B2_REGION`, and `B2_PUBLIC_URL_BASE`.

## Plan

1. Replace legacy key-id, endpoint, and public-URL aliases in runtime config,
   `.env.example`, setup checks, tests, and docs.
2. Derive the B2 S3 endpoint from `B2_REGION` so users no longer configure an
   endpoint alias.
3. Update the boto3 user agent string to include the Backblaze sample-suite
   marker while preserving the sample identity.
4. Validate `B2_REGION` against a strict Backblaze region pattern before
   building any outbound S3 endpoint.
5. Document the rolling-deploy migration path: add standardized variables
   alongside legacy variables, deploy this release, then remove legacy
   variables after old instances are drained.
6. Run backend lint/tests plus structure checks and frontend lint for the
   touched JavaScript setup script.
