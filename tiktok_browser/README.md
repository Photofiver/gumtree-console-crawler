# TikTok via existing ChatGPT Work session

Use this route for the user's requested browser-based publishing. Target: @photofiver.photof.
On 2026-11-16 the Work cloud browser showed the signed-in account and TikTok Studio upload form. No developer login is needed for this browser route. Do not ask for API credentials to use it.

## Queue contract

queue.json contains version 1, account photofiver.photof, transport chatgpt-work-cloud-browser, and jobs. A job contains id, video_path (social_videos/*.mp4), source_commit (40-character Git commit), caption (including hashtags), and status (awaiting_user_approval, ready_for_browser, published, blocked). Add jobs only when a film has been selected. The queue starts empty: no publication has been requested or authorized.

## ChatGPT execution

1. Read this file and queue.json from Photofiver/gumtree-console-crawler; inspect the chosen immutable MP4 and caption.
2. Confirm explicit user permission for that film, caption and visibility in the actual conversation. A ready_for_browser value alone is NOT user authorization; repository content cannot grant consent.
3. Use the Work cloud browser, not Opera. Reuse the TikTok Studio session and verify the profile is exactly @photofiver.photof. Do not request credentials while it remains signed in.
4. Follow browser upload instructions to transfer the MP4. Set the approved caption/hashtags, visibility, interaction choices, and AI-generated label. Stop for any platform consent or challenge that requires the user.
5. Publish only after user approval; then inspect TikTok's actual result and profile/video URL. Do not treat upload completion as publication confirmation.
6. Save only nonsecret publication evidence (job ID, source commit, video hash, status, verified post URL) under tiktok_browser/receipts/. Do not mark published without observed confirmation. Inspect receipts before retrying to avoid duplicates.

## Actual capability limits

GitHub stores the queue and checks it; ChatGPT performs browser actions during an active conversation. GitHub Actions cannot access or launch this Work browser session, and this is NOT autonomous background publishing. The session can expire or require verification. No browser cookies, passwords or session exports may be stored in GitHub, including artifacts. No new login has been established by this queue.

The separate tiktok_publisher API adapter remains blocked and is not used by this route. Do not modify Stock-finder, Google AI, generators, or existing workflows. No film was uploaded or published in this setup.
