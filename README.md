# AiEnvoy YouTube Short automation

This standalone workflow generates a 9:16 Short using AiEnvoy's published `POST https://api.aienvoy.dev/api/v1/videos/generate` endpoint, downloads the finished MP4, preserves its aspect ratio, and optionally uploads it to YouTube using OAuth.

## Setup

Put these files in the repository root (preserve `.github/workflows/`). Create GitHub Actions secret `AI_ENVOY_KEY` using the key from AiEnvoy. For optional publishing also configure `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, and `YT_REFRESH_TOKEN`.

**Important API documentation gap:** The public AiEnvoy page confirms async generation and a task ID, but does not expose a verified task-status URL. If the initial response provides `status_url`/`poll_url`, the script uses it. Otherwise set GitHub Actions variable `AI_ENVOY_STATUS_URL_TEMPLATE` to the **verified, documented** status endpoint with `{task_id}`, e.g. `https://api.aienvoy.dev/EXACT/DOCUMENTED/PATH/{task_id}`. This example is a placeholder, not a real endpoint. Without it the job stops with a clear error after creating a task. Don't guess a URL because generation may cost credits.

The workflow defaults to manual runs and **no YouTube publishing**. Enable `publish` when ready, choose `public` for public upload. Some YouTube API projects are restricted to private video uploads until audited. YouTube credentials must have the `youtube.upload` scope.

To check the outgoing paid generation request without sending it:
`python aienvoy_short.py --dry-run`

AiEnvoy's story API can charge credits. The workflow does not automatically retry the generation POST or run on a schedule. A single request may create a billable task; always test privately first. The output is normalized to 1080x1920 without distortion, preserving all source pixels with black letterboxing if needed.

No upload is attempted unless a valid MP4 is produced; Git is never used to store the video.
