# Automatic AI Stickman Shorts

This package generates a five-scene vertical comedy video automatically using a Cloudflare Workers AI text model, FLUX.1 Schnell images, Kokoro ONNX narration, and FFmpeg.

## Install

Copy `.github/workflows/create-ai-shorts.yml`, `auto_spec.py`, `gen_images.py`, `shorts.py`, and `requirements-shorts.txt` into the indicated paths in the `Production` branch. Commit `jobs/example/spec.json` only if you want an example.

In GitHub Repository Settings → Secrets and variables → Actions, configure:
- `CF_ACCOUNT_ID`: Cloudflare account identifier
- `CF_API_TOKEN`: scoped token with Workers AI access

Optionally configure `CF_TEXT_MODEL` as a repository variable and add its environment mapping to the workflow (default model: `@cf/meta/llama-3.1-8b-instruct`).

## Run

In Actions → **Generate AI Short (Cloudflare + Kokoro)** → Run workflow:
- Leave `spec_path` blank to generate a **new** storyboard automatically.
- Optionally fill `topic`, such as `A stickman tries to teach a robot to make coffee`.
- Or set `spec_path` to `jobs/example/spec.json` to render an existing storyboard.

The workflow also runs once a day at 09:10 Asia/Manila, choosing a rotating topic. Scheduled events are subject to GitHub timing delays and repository Actions configuration.

Output is downloadable under each Actions run as an MP4 artifact; the generated scene JSON/images are also available as a separate artifact. The workflow never pushes videos to Git. Current repository size issues must be resolved independently.

## Notes

`gen_images.py` sends only `prompt` and `steps` to FLUX.1 Schnell. `seed` is intentionally not passed because it caused an HTTP 400 input schema error. Cloudflare quota / rate limits and available text models depend on the account. `auto_spec.py` fails visibly if the text model returns malformed JSON rather than rendering corrupted scenes.
