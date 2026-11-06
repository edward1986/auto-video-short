#!/usr/bin/env python3
"""Generate a 20-image Shorts spec from a random Short Stories API fable.

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
MOVES = ["zoom_in", "pan_right", "zoom_out", "pan_left"]
TRANSITIONS = ["cut", "punch", "cut", "whip"]


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


def make_prompt(source):
    if isinstance(source, str):
        story_block = f"TOPIC: {source}"
        constraint = "Create an original family-friendly story based on this topic."
    else:
        story_block = (
            f"TITLE: {source['title']}\nAUTHOR: {source['author']}\n"
            f"SOURCE STORY: {source['story']}\nMORAL: {source['moral']}"
        )
        constraint = (
            "Adapt the actual fable faithfully: characters, species, events and outcome. "
            "Never depict animals as stickmen. Keep difficult endings non-graphic. "
            "The final scene must convey the moral in easy English."
        )
    return f"""Adapt this into a vertical animated STORYBOARD containing EXACTLY FIVE KEY STORY BEATS.
{story_block}
{constraint}
Return one strictly valid JSON object and NOTHING else:
{{"title":"story title","scenes":[{{"prompt":"visible 2D cartoon action in a portrait composition","narration":"one summary sentence","shot_narrations":["short line for shot 1","short line for shot 2","short line for shot 3","short line for shot 4"]}}]}}
Rules: exactly five scene objects (not twenty); each prompt 35-90 words, concrete physical actions,
consistent species, colors, location, clothing, background and characters; no visible text.
Each shot_narrations item is 4-10 easy-English words describing that shot and continuing the actual fable; exactly 4 nonempty strings per beat. Every one of the 20 pictures MUST have spoken narration. Each beat narration is a short optional summary (7-15 words); keep scene order and moral accurate.
JSON only, escape any internal quotation marks. Do not output markdown or trailing commas.
"""


def parse_five(content):
    raw = extract_json(content)
    if not isinstance(raw, dict) or not isinstance(raw.get("scenes"), list) or len(raw["scenes"]) != 5:
        raise ValueError("AI must return exactly five key story beats")
    for index, scene in enumerate(raw["scenes"], 1):
        if not isinstance(scene, dict) or not isinstance(scene.get("prompt"), str) or not isinstance(scene.get("narration"), str):
            raise ValueError(f"Invalid scene {index}: missing prompt/narration")
        if len(scene["prompt"].strip()) < 20 or len(scene["narration"].strip()) < 10:
            raise ValueError(f"Invalid scene {index}: prompt or narration too short")
        lines = scene.get("shot_narrations")
        if lines is not None and (
            not isinstance(lines, list) or len(lines) != 4
            or any(not isinstance(item, str) or len(item.strip()) < 2 for item in lines)
        ):
            raise ValueError(f"Scene {index} must have exactly four nonempty shot_narrations")
    return raw


def fallback_storyboard(source):
    """Keep GitHub Actions running if Cloudflare returns invalid JSON repeatedly.

    The fallback uses ONLY the supplied original fable, not invented story details.
    """
    text = source if isinstance(source, str) else source["story"]
    chunks = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    if not chunks:
        chunks = [text]
    title = source[:85] if isinstance(source, str) else source["title"]
    moral = "" if isinstance(source, str) else source["moral"].strip().rstrip(".")
    scenes = []
    for index in range(5):
        position = min(len(chunks)-1, (index * len(chunks)) // 5)
        chunk = chunks[position]
        if index == 4 and moral:
            narration = "The lesson is: " + moral.rstrip(".") + "."
            cue = f"Conclude the fable with the consequences and its lesson: {moral}."
        else:
            narration = chunk
            cue = chunk
        # Limit narration duration in long-source fallback
        words = narration.split()
        if len(words) > 18:
            narration = " ".join(words[:18]).rstrip(",;:") + "."
        visual = (
            "Family friendly 2D illustrated storybook frame, portrait 9:16. "
            f"Story: {title}. The characters, species, setting and actions must remain "
            f"faithful to this source: {text[:750]}. "
            f"At this moment, depict: {cue}. "
            "Consistent character designs, expressive poses, cinematic soft lighting, no words or text."
        )[:1250]
        scenes.append({"prompt": visual, "narration": narration})
    return {"title": title, "scenes": scenes}


def cloudflare_content(payload):
    result = payload.get("result") or {}
    if isinstance(result, dict):
        content = result.get("response")
        if content:
            return content
        choices = result.get("choices") or []
        if choices:
            return (choices[0].get("message") or {}).get("content") or choices[0].get("text")
    raise ValueError("Text model returned no response content")


def call_ai(story):
    model = os.getenv("CF_TEXT_MODEL", "@cf/meta/llama-3.1-8b-instruct").strip()
    prompt = make_prompt(story)
    accounts = list(cloudflare_accounts())
    if not accounts:
        raise RuntimeError("No Cloudflare accounts configured")
    malformed = []
    for index, (label, account_id, token) in enumerate(accounts):
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        # Retry malformed JSON on the SAME account (never reattempt an exhausted one).
        for attempt in range(1, 4):
            if attempt == 1:
                instruction = prompt
            else:
                instruction = prompt + (
                    "\nIMPORTANT: previous response was INVALID JSON. Use simple descriptions, "
                    "no nested objects, exact 5 scenes, escape quotes, and close every brace."
                )
            body = json.dumps({"messages": [
                {"role": "system", "content": "You write well-formed JSON storyboards. Respond with exactly one JSON object."},
                {"role": "user", "content": instruction},
            ], "max_tokens": 2900, "temperature": 0.25}).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    payload = json.load(resp)
            except urllib.error.HTTPError as exc:
                details = exc.read(1500).decode("utf-8", "replace")
                try:
                    error_payload = json.loads(details)
                except json.JSONDecodeError:
                    error_payload = details
                if daily_quota_exhausted(exc.code, error_payload):
                    print(f"{label}: daily neurons exhausted", flush=True)
                    if index+1 < len(accounts):
                        print(f"Switching to {accounts[index+1][0]} account", flush=True)
                    break
                raise RuntimeError(f"{label} text HTTP {exc.code}: {details[:400]}") from exc
            if not isinstance(payload, dict):
                malformed.append(f"{label} attempt {attempt}: invalid Cloudflare response")
                continue
            if payload.get("success") is False:
                if daily_quota_exhausted(429, payload):
                    print(f"{label}: daily neurons exhausted", flush=True)
                    break
                raise RuntimeError(f"{label} text model error: {payload.get('errors')}")
            try:
                raw = parse_five(cloudflare_content(payload))
                print(f"Story beats generated on {label} account (attempt {attempt})", flush=True)
                return raw
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                malformed.append(f"{label} attempt {attempt}: {type(exc).__name__}: {str(exc)[:125]}")
                print(f"INVALID_AI_JSON: {label} attempt {attempt}/3; retrying if possible", flush=True)
        else:
            # Don't switch accounts just because the model produced bad JSON.
            break
    if malformed:
        print("AI JSON retries unsuccessful; generating safe source-based storyboard.", flush=True)
        for message in malformed:
            print("WARNING", message, flush=True)
        return fallback_storyboard(story)
    raise RuntimeError("All configured Cloudflare accounts have exhausted their daily neuron allocations")


CAMERAS = [
    "A wide establishing shot with the full scene and clear character positions.",
    "A medium shot revealing the characters' expressions and their reactions.",
    "A closer side-angle shot showing the key physical action in progress.",
    "A cinematic reaction shot with the characters and consequences in the same setting.",
]


def distribute_narration(text, count=4):
    """Fallback for older model responses: distribute existing dialogue across shots.

    The spoken words stay in their original order without repeating an entire
    sentence four times. This is used only when the AI omits shot_narrations.
    """
    words = str(text).strip().split()
    if not words:
        raise ValueError("Narration cannot be empty")
    if len(words) < count:
        # Extremely short AI text: repeated as a last resort to avoid silent shots.
        return [str(text).strip()] * count
    n = len(words)
    boundaries = [round(i * n / count) for i in range(count + 1)]
    return [" ".join(words[boundaries[i]:boundaries[i + 1]]) for i in range(count)]


def validate_and_build(raw, source):
    """Expand 5 narrated story beats into 20 uniquely composed image segments.

    5 x 4 scenes keeps the Cloudflare LLM JSON small enough to avoid truncation.
    Every image has its OWN spoken line (no silent frames by default).
    If the LLM does not supply four lines for each beat, the original
    narration is split across the four images rather than duplicated.
    """
    raw = parse_five(raw)
    segments = []
    for beat_idx, scene in enumerate(raw["scenes"]):
        spoken_lines = scene.get("shot_narrations") or distribute_narration(scene["narration"])
        for shot_idx, camera in enumerate(CAMERAS):
            idx = beat_idx * 4 + shot_idx
            visual = scene["prompt"].strip()
            segments.append({
                "type": "still",
                "path": f"scene-{idx+1:02d}.png",
                "prompt": (
                    f"Image {idx+1} of a 20-image continuous story. {visual} "
                    f"SHOT {shot_idx+1} of beat {beat_idx+1}: {camera} "
                    "Show an original coherent frame of the SAME ongoing action. "
                    "Keep the characters, setting, clothing and palette consistent. "
                    "No printed text, captions or watermarks."
                )[:1800],
                "move": MOVES[shot_idx],
                "transition": TRANSITIONS[shot_idx] if idx else "cut",
                "min": 2.4,
                "pad": 0.35,
                "narration": spoken_lines[shot_idx].strip(),
            })
    if len(segments) != 20:
        raise AssertionError("Expected exactly 20 scenes")
    if not all(segment["narration"] for segment in segments):
        raise AssertionError("Every image must have narration")
    source_title = source["title"] if isinstance(source, dict) else str(source)
    title = str(raw.get("title") or source_title).strip()[:90]
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:45] or "fable-short"
    suffix = os.getenv("GITHUB_RUN_ID") or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    spec = {
        "slug": f"{slug}-{suffix}", "aspect": "9:16", "voice": "am_puck",
        "speed": 1.05, "music_gain": 0.32, "segments": segments,
    }
    if isinstance(source, dict):
        spec["source"] = {
            "provider": "shortstories-api", "id": source["_id"],
            "title": source["title"], "author": source["author"],
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
    print(f"Generated {output} with {len(spec['segments'])} image scenes")
    print("Source:", source if isinstance(source, str) else source["title"])
    print("Slug:", spec["slug"])


if __name__ == "__main__":
    main()
