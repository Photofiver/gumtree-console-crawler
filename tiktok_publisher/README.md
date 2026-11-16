# Isolated TikTok publication adapter — setup BLOCKED

Target: `@photofiver.photof`. This directory and `.github/workflows/tiktok-isolated.yml`
are independent of all generators, Google AI and the trading repository.
No scheduled publishing, cookie export, token files, or changes to other workflows.
Only `contents: read`; credentials are injected from GitHub Secrets, never committed.

## Observed 2026-11-16

- Work cloud browser is signed in to the exact account and displays TikTok Studio upload.
- September history describes browser publication, not a working GitHub API bridge.
- Existing GitHub diagnostic run 43799301475 found none of the four known access-token
  secrets or two refresh-token secrets. This is NOT a successful API permission test.
- TikTok for Developers requires separate email/password login. App inventory,
  approval, OAuth redirect and granted scopes are not yet inspectable.
- Official Direct Post guidelines exclude private/internal tools for accounts the
  developer/team manages. Do not misrepresent this project to obtain an audit.
- Public Direct Post needs app approval/audit, user OAuth grant `video.publish`,
  a valid token and a compliant consent/preview UI. Creator-info success proves the
  scope and account but DOES NOT prove app audit or public publishing authorization.

## Workflow

Pushes touching only the new integration run tests and **preflight only**. Manual
`workflow_dispatch` supports `preflight`, `publish`, and `status`. No token or a denied
API scope fails the run and produces a sanitized `tiktok-result.json` artifact.
Preflight calls the real `creator_info/query` endpoint when a token exists; no init,
upload or publication endpoint is called. It verifies account, probes MP4 duration,
and returns available privacy choices plus SHA256 for a later approval.

Publication implementation is staged, NOT enabled or end-to-end verified. It needs:

1. An eligible TikTok app and secure OAuth callback/token lifecycle implementation.
   Access token in `TIKTOK_ACCESS_TOKEN`; no user passwords or cookies in Actions.
   Refresh-token rotation and persistence are not configured: permanent unattended
   authorization cannot currently be promised. Never put auth codes in workflow inputs.
2. TikTok URL-property verification for
   `https://raw.githubusercontent.com/Photofiver/gumtree-console-crawler/`.
   Server-hosted MP4 uses PULL_FROM_URL. This prefix's acceptance has NOT been verified;
   if TikTok cannot verify it, an owned verified media host and adapter change are needed.
   Set `TIKTOK_VERIFIED_URL_PREFIX` only after actual verification.
3. A compliant review flow displaying current account info, video preview and exact
   caption/hashtags, explicit visibility selection, interaction and commercial choices,
   and applicable music/branded-content consent. Set `TIKTOK_API_READY=true` ONLY after
   confirming app eligibility, approvals, lifecycle and this review flow.
4. User approval for the specific film, caption and settings. The manual `consent`
   input must equal `PUBLISH @photofiver.photof <SHA256>` from preflight. An operator
   must not supply this without that user's explicit approval.

`post_settings` is JSON with `privacy_level` (no default), `allow_comment`, `allow_duet`,
`allow_stitch` (all default false), `brand_content_toggle`, `brand_organic_toggle`,
`music_usage_confirmed`, and, if needed, `branded_content_policy_confirmed`.
AI label is always enabled. `caption` contains both description and hashtags.

On publication the adapter pins the media URL to the run's immutable commit,
persists `publish_id` immediately, then checks the status endpoint. A timeout is
pending, never success. Use `status` with the receipt rather than re-publishing.
GitHub rerun attempts are blocked from publishing. A new manual run could still
duplicate an earlier post: always inspect prior receipts before authorizing one.
`PUBLISH_COMPLETE` confirms completion; public links appear only for IDs returned by
TikTok after public moderation. No live posting test has been authorized or performed.

## Primary references

- https://developers.tiktok.com/docs/en/content-sharing-guidelines
- https://developers.tiktok.com/docs/en/content-posting-api-reference-query-creator-info
- https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post
- https://developers.tiktok.com/docs/en/content-posting-api-reference-get-video-status
