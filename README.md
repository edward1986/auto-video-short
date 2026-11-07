# Technology Then vs. Now — Kokoro Voice Edition

This version replaces the earlier `espeak-ng` narration with **Kokoro ONNX neural TTS**. It keeps the existing split-screen technology illustrations, original synthesized background music, transition sounds, 9:16 video rendering, topic rotation, daily schedule, and YouTube uploader.

## Install in GitHub

Copy the ZIP contents into your `Production` branch, preserving `.github/workflows/technology-then-now.yml`.

Files to replace/add:
- `.github/workflows/technology-then-now.yml`
- `generate_tech_short.py`
- `requirements-tech.txt`
- `topics.json`
- `upload_tech_youtube.py`

The workflow downloads and caches these official Kokoro ONNX assets automatically:
- `kokoro-v1.0.int8.onnx`
- `voices-v1.0.bin`

You do **not** need a Cloudflare AI key or an external TTS account. GitHub Actions still uses `espeak-ng` as a local phonemizer dependency for Kokoro, but it no longer uses its synthesized voice for narration.

## Voice selection

Run **Technology Then vs Now - YouTube Shorts** under GitHub Actions. Choose one of the voice inputs:
- `am_puck` (default)
- `af_heart`
- `am_adam`
- `af_bella`

You can set `KOKORO_SPEED` as a job environment variable or pass `--voice-speed 1.08` to the generator.

## YouTube upload

Use the same repository secrets as your existing YouTube workflows:
- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_REFRESH_TOKEN`

Manual runs publish only when `publish` is checked. Scheduled runs request public visibility. YouTube may impose API restrictions independent of the workflow.

## Local usage

Install `ffmpeg`, `espeak-ng`, Python dependencies from `requirements-tech.txt`, then download the Kokoro model assets to `KOKORO_DIR` (default `~/.cache/kokoro`).

```bash
python generate_tech_short.py --topic phones --voice am_puck --voice-speed 1.08 --output output.mp4
```

## Testing

Python compilation and YAML structure have been checked. The complete Kokoro inference and YouTube upload require model files and credentials; neither was run here. The previously tested original generator confirmed MP4 H.264/AAC rendering before this TTS change.
