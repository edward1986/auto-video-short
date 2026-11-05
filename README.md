# Automated YouTube Public Shorts — ready-to-copy files

Copy these files into the ROOT of your GitHub repository, preserving `.github/workflows/create-ai-shorts.yml`.

- `auto_spec.py` creates the story specification automatically.
- `gen_images.py` calls Cloudflare FLUX.1 Schnell without unsupported seed and creates a neutral illustration for moderation-rejected prompts.
- `shorts.py` is your supplied assembler with 9:16 image fit and captions.
- `upload_youtube.py` uploads the final MP4 to YouTube with `privacyStatus=public`.
- `requirements-shorts.txt` contains Python runtime requirements.

Add GitHub Actions secrets: `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

Run Actions > Generate AI Short (Cloudflare + Kokoro) > Run workflow, or use the daily schedule (09:10 Philippines).

Videos are saved as Actions artifacts, not committed to Git. YouTube can force private uploads when the API project isn't verified. An OAuth token with youtube.upload scope for your channel is needed.

IMPORTANT: YouTube uploads are irreversible public actions; the workflow is configured to publish automatically on success. Test on an authorized channel.
