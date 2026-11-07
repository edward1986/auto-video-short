# Technology Then vs. Now — YouTube Shorts GitHub Action

Produces a vertical 720×1280 Short that compares old and modern technologies, uses custom drawn split-screen illustrations, English voiceover via `espeak-ng`, original synthesized background music, and transition sounds. No Cloudflare image credits, third-party footage, or paid stock images required.

## Install

Copy the following into the **Production** branch of `edward1986/auto-video-short`:

- `.github/workflows/technology-then-now.yml`
- `generate_tech_short.py`
- `upload_tech_youtube.py`
- `requirements-tech.txt`
- `topics.json`

Add GitHub Actions secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, and `YT_REFRESH_TOKEN`. Existing secrets from your other YouTube workflows can be reused. The YouTube Data API must be enabled on the Google Cloud project and the refresh token must authorize `youtube.upload` for the correct channel. YouTube may restrict public uploads from unverified API projects.

Go to **Actions → Technology Then vs Now - YouTube Shorts → Run workflow**. Set topic (`auto` rotates), publish (`true` by default), and privacy (`public` by default).

The workflow is scheduled **daily at 09:10 Philippine time** (01:10 UTC) and scheduled runs **automatically request Public YouTube uploads**. To disable automatic publication, remove the `schedule:` section from the workflow or modify the publish condition. GitHub scheduled workflows only run from the repository's default branch; if `Production` isn't the default branch, manual dispatch works on `Production` but the daily schedule will not execute until the workflow is present on the default branch. GitHub may delay scheduled runs.

## Content rotation

`topics.json` contains 12 curated comparisons (phones, cameras, storage, music, computers, lighting and more). Auto mode selects an entry using `GITHUB_RUN_NUMBER`, so consecutive workflow runs cycle through different subjects. After all 12, entries repeat unless you add more.

To add a comparison, edit `topics.json` and add `id`, `topic`, `then`, `now`, `then_year`, `now_year`, `fact`, `change`, `takeaway`, and `symbol` fields.

## Output files

- `output.mp4`: 9:16 video with English narration, music and motion-free illustrated slides
- `tech_metadata.json`: topic, title, description, duration, run number
- `youtube-upload.json`: YouTube URL and ID (only if published successfully)

This workflow **does not commit videos to Git**, preventing repository-size growth. If uploading fails, the job should report failure; the MP4 artifact is still saved.

## Local run

Install ffmpeg and espeak-ng, then `pip install -r requirements-tech.txt`.

```bash
python generate_tech_short.py --topic phones --output output.mp4
```

Output is illustrated with Pillow, not Wikimedia photographs. Narration uses a local synthetic voice and can be upgraded later to Kokoro. The curated copy is designed to avoid exact technical performance claims without references.
