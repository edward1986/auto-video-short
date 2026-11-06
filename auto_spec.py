#!/usr/bin/env python3
"""Generate a five-scene Shorts spec from a random Short Stories API fable.

Usage:
    python3 auto_spec.py jobs/auto/spec.json
    python3 auto_spec.py jobs/auto/spec.json "optional custom topic"

Environment:
    CF_ACCOUNT_ID, CF_API_TOKEN
    CF_BACKUP_ACCOUNT_ID, CF_BACKUP_API_TOKEN (optional)
    CF_BACKUP_ACCOUNT_ID_2, CF_BACKUP_API_TOKEN_2 (optional third account)
    CF_TEXT_MODEL (optional)
    SHORT_STORIES_API_URL (optional; default https://shortstories-api.onrender.com/)
    SHORTS_TOPIC (optional; overrides API story when supplied)
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

STORIES_URL = "https://shortstories-api.onrender.com/"
MOVES = ["zoom_in", "pan_right", "zoom_out", "pan_left", "zoom_in"]
TRANSITIONS = ["cut", "punch", "cut", "whip", "flash"]


def extract_json(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise ValueError("AI response is not JSON text")
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip(), flags=re.I)
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        a, b = value.find("{"), value.rfind("}")
        if a < 0 or b <= a:
            raise
        return json.loads(value[a:b + 1])


def fetch_story():
    """GET / returns one randomly selected story; no API key is needed."""
    url = os.getenv("SHORT_STORIES_API_URL", STORIES_URL).strip()
    if not url.startswith("https://"):
        raise ValueError("SHORT_STORIES_API_URL must be an HTTPS URL")
    last_error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": "ShortsSpecBot/1.0"},
                method="GET",
            )
            with urllib.request.urlopen(request, timeout=35) as response:
                raw = json.load(response)
            if not isinstance(raw, dict):
                raise ValueError("Story API must return a JSON object")
            for key in ("title", "story", "moral"):
                if not isinstance(raw.get(key), str) or not raw[key].strip():
                    raise ValueError(f"Story API response missing nonempty {key!r}")
            return {
                "_id": str(raw.get("_id", "")),
                "title": raw["title"].strip(),
                "author": str(raw.get("author") or "Unknown").strip(),
                "story": raw["story"].strip(),
                "moral": raw["moral"].strip(),
            }
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"Story API HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        if attempt < 2:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Could not fetch a story from {url}: {last_error}")


def daily_quota_exhausted(status, payload):
    """Detect Cloudflare Workers AI daily neuron exhaustion (code 4006)."""
    if isinstance(payload, dict):
        errors = payload.get("errors") or []
        if any(isinstance(e, dict) and str(e.get("code")) == "4006" for e in errors):
            return True
        message = " ".join(str(e.get("message", "")) for e in errors if isinstance(e, dict))
    else:
        message = str(payload)
    msg = message.lower()
    return status == 429 and (
        "daily free allocation" in msg
        or "daily_free_limit_reached" in msg
        or ("neuron" in msg and ("limit" in msg or "allocation" in msg))
    )


def cloudflare_accounts():
    """Use primary -> backup 1 -> backup 2, if configured.

    The fallback is intended for separately authorized Cloudflare accounts,
    subject to Cloudflare's service terms and account restrictions.
    """
    credentials = [
        ("primary", "CF_ACCOUNT_ID", "CF_API_TOKEN"),
        ("backup 1", "CF_BACKUP_ACCOUNT_ID", "CF_BACKUP_API_TOKEN"),
        ("backup 2", "CF_BACKUP_ACCOUNT_ID_2", "CF_BACKUP_API_TOKEN_2"),
    ]
    for label, id_key, token_key in credentials:
        account_id = os.getenv(id_key, "").strip()
        token = os.getenv(token_key, "").strip()
        if not account_id and not token:
            if label == "primary":
                raise RuntimeError(f"Set both {id_key} and {token_key}")
            continue
        if not account_id or not token:
            raise RuntimeError(f"Set both {id_key} and {token_key}")
        yield (label, account_id, token)


def call_ai(story):
    model = os.getenv("CF_TEXT_MODEL", "@cf/meta/llama-3.1-8b-instruct").strip()

    if isinstance(story, str):
        source = f"USER TOPIC: {story}"
        directions = "Create an original family-friendly story based on the user's topic."
    else:
        source = (
            f"FABLE TITLE: {story['title']}\n"
            f"ATTRIBUTION: {story['author']}\n"
            f"SOURCE STORY: {story['story']}\n"
            f"MORAL: {story['moral']}"
        )
        directions = (
            "Adapt this source fable, not a newly invented story. Preserve the real "
            "characters, causal sequence, ending, and moral. Do NOT make every character "
            "a stickman; show the animals or people described in the fable. "
            "Use an age-appropriate, non-graphic depiction if the ending is harsh. "
            "Scene five must communicate the source moral in easy language."
        )

    prompt = f"""Create a 25–40 second vertical illustrated YouTube Short based on the source below.

{source}

{directions}
Return ONLY JSON exactly in the format:
{{"title":"short catchy title","scenes":[{{"prompt":"full visual description","narration":"one spoken sentence"}}]}}
Rules:
- EXACTLY 20 scenes with a faithful beginning, conflict, consequences, ending and moral.
- Maintain the same character designs, clothing, animal colors, background and lighting across scenes.
- All images: polished 2D animated illustration, portrait framing, distinct expressions, no written words.
- Each visual prompt: 50–250 words describing specific visible action and framing.
- Each narration: 7–18 easy-English words. Keep narration faithful to source; do not fabricate facts.
- Do not include text in images, brand names, real people, or graphic injuries.
- Only valid JSON, with no markdown.
"""
    body = json.dumps(
        {"messages": [
            {"role": "system", "content": "You adapt supplied fables into accurate visual storyboards. Output JSON only."},
            {"role": "user", "content": prompt},
        ], "max_tokens": 2300, "temperature": 0.4}
    ).encode("utf-8")
    accounts = list(cloudflare_accounts())
    payload = None
    for index, (label, account_id, token) in enumerate(accounts):
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        request = urllib.request.Request(
            url, data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            details = exc.read(2000).decode("utf-8", "replace")
            try:
                error_payload = json.loads(details)
            except json.JSONDecodeError:
                error_payload = details
            if daily_quota_exhausted(exc.code, error_payload):
                print(f"{label.capitalize()} Cloudflare account exhausted its daily neuron allocation.", flush=True)
                if index + 1 < len(accounts):
                    print(f"Switching to {accounts[index + 1][0]} Cloudflare account for text generation.", flush=True)
                    continue
                raise RuntimeError("All configured Cloudflare accounts have exhausted their daily neuron allocations") from exc
            # Do not expose tokens or retry invalid requests/authentication errors.
            raise RuntimeError(f"{label.capitalize()} Cloudflare text model HTTP {exc.code}: {details[:600]}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"{label.capitalize()} Cloudflare returned an invalid response")
        if payload.get("success") is False:
            if daily_quota_exhausted(429, payload):
                print(f"{label.capitalize()} Cloudflare account exhausted its daily neuron allocation.", flush=True)
                if index + 1 < len(accounts):
                    print(f"Switching to {accounts[index + 1][0]} Cloudflare account for text generation.", flush=True)
                    continue
                raise RuntimeError("All configured Cloudflare accounts have exhausted their daily neuron allocations")
            raise RuntimeError(f"{label.capitalize()} Cloudflare text model error: {payload.get('errors')}")
        print(f"Cloudflare text spec generated using {label} account.", flush=True)
        break
    if payload is None:
        raise RuntimeError("No Cloudflare response received")
    result = payload.get("result") or {}
    content = result.get("response") if isinstance(result, dict) else None
    if not content and isinstance(result, dict):
        choices = result.get("choices") or []
        if choices:
            content = (choices[0].get("message") or {}).get("content") or choices[0].get("text")
    if not content:
        raise ValueError("Cloudflare text model returned no response")
    return extract_json(content)


def validate_and_build(raw, source):
    if not isinstance(raw, dict) or not isinstance(raw.get("scenes"), list) or len(raw["scenes"]) != 5:
        raise ValueError("AI must provide exactly five scenes")
    segments = []
    for i, scene in enumerate(raw["scenes"]):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene {i+1} must be an object")
        visual, narration = scene.get("prompt"), scene.get("narration")
        if not isinstance(visual, str) or not 30 <= len(visual.strip()) <= 1400:
            raise ValueError(f"Scene {i+1} requires a 30–1400 character visual prompt")
        if not isinstance(narration, str) or not 10 <= len(narration.strip()) <= 250:
            raise ValueError(f"Scene {i+1} requires a short narration sentence")
        segments.append({
            "type": "still",
            "path": f"scene-{i+1:02d}.png",
            "prompt": visual.strip(),
            "move": MOVES[i],
            "transition": TRANSITIONS[i],
            "min": 3.0,
            "pad": 0.5,
            "narration": narration.strip(),
        })

    source_title = source["title"] if isinstance(source, dict) else str(source)
    title = str(raw.get("title") or source_title).strip()[:90]
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:45] or "fable-short"
    suffix = os.getenv("GITHUB_RUN_ID") or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    spec = {
        "slug": f"{slug}-{suffix}",
        "aspect": "9:16",
        "voice": "am_puck",
        "speed": 1.05,
        "music_gain": 0.32,
        "segments": segments,
    }
    if isinstance(source, dict):
        spec["source"] = {
            "provider": "shortstories-api",
            "id": source["_id"],
            "title": source["title"],
            "author": source["author"],
            "moral": source["moral"],
            "url": os.getenv("SHORT_STORIES_API_URL", STORIES_URL).strip(),
        }
    return spec


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit("Usage: python auto_spec.py jobs/auto/spec.json [optional topic]")
    output = Path(sys.argv[1])
    override = (sys.argv[2] if len(sys.argv) == 3 else os.getenv("SHORTS_TOPIC", "")).strip()
    source = override if override else fetch_story()
    raw = call_ai(source)
    spec = validate_and_build(raw, source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {output} with {len(spec['segments'])} scenes")
    print("Source:", source if isinstance(source, str) else source["title"])
    print("Slug:", spec["slug"])


if __name__ == "__main__":
    main()
