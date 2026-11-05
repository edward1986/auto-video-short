# Trivia Time: scheduled YouTube Shorts

Copy all files into the root of your `Production` branch, preserving `.github/workflows/trivia-time-youtube.yml`.

## GitHub Actions secrets

- `CF_ACCOUNT_ID`: Cloudflare account ID
- `CF_API_TOKEN`: Workers AI API token with Workers AI access
- `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`: OAuth2 credentials authorized for **YouTube Data API v3** `youtube.upload` scope on the intended channel. Obtain refresh token through an OAuth consent flow once. Do not use a YouTube API key; uploads require OAuth. Never commit credentials.

## Run

GitHub -> Actions -> **Trivia Time - Generate and Publish YouTube Short** -> Run workflow.

Manual runs default to **private** for safe preview, and you can select `public` to publish. Scheduled runs are set to **public**, every day at 09:10 in the Philippines. To preview all runs first, change the `YT_PRIVACY` workflow expression to `'private'`.

The default question comes from a **reviewed local trivia bank**. Set `use_ai=true` to generate new questions with Workers AI; AI-generated facts need verification before public use. `topic` filters the curated bank when AI mode is off.

Pipeline: `auto_trivia_spec.py` -> `gen_images.py` (FLUX, no unsupported seed parameter) -> Kokoro model -> `trivia_render.py` -> MP4 Actions artifact -> `upload_youtube.py`.

No MP4 is committed to Git. An existing repository size quota violation can still affect GitHub pushes until old history is cleaned or Support resolves it.

## Video design

1080x1920, visible question and four labeled answers, timer countdown, separate green correct-answer reveal, spoken question and explanation, safe margins. Generated content is one question per video.

## OAuth reminder

A `YT_REFRESH_TOKEN` must belong to a Google account authorized to upload to the desired channel. If you copied old OAuth credentials into public source code, revoke and rotate them before using this workflow.
