#!/usr/bin/env python3
"""Generate a validated Shorts spec using Cloudflare Workers AI.
Usage: python auto_spec.py jobs/auto/spec.json [optional topic]
Environment: CF_ACCOUNT_ID, CF_API_TOKEN, optional CF_TEXT_MODEL, SHORTS_TOPIC.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

TOPICS = [
    'A stickman tries to work from home while a mischievous cat interrupts every meeting',
    'A stickman buys a robot vacuum that believes it is the household boss',
    'A stickman attempts to cook breakfast and accidentally invents a new sport',
    'A stickman goes to the gym and mistakes the machines for modern art',
    'A stickman orders a tiny coffee and receives a gigantic cup',
    'A stickman tries to fix a dripping faucet with increasingly silly solutions',
    'A stickman misses a bus but discovers an absurd alternative commute',
    'A stickman learns to dance from a very confident pigeon',
]
MOVES = ['zoom_in', 'pan_right', 'zoom_out', 'pan_left', 'zoom_in', 'pan_up']
TRANSITIONS = ['cut', 'punch', 'cut', 'whip', 'flash', 'cut']


def extract_json(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise ValueError('AI response is not JSON text')
    value = value.strip()
    value = re.sub(r'^```(?:json)?\s*|\s*```$', '', value, flags=re.I)
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        a, b = value.find('{'), value.rfind('}')
        if a < 0 or b <= a:
            raise
        return json.loads(value[a:b + 1])


def call_ai(topic):
    acc = os.environ.get('CF_ACCOUNT_ID', '').strip()
    token = os.environ.get('CF_API_TOKEN', '').strip()
    model = os.environ.get('CF_TEXT_MODEL', '@cf/meta/llama-3.1-8b-instruct').strip()
    if not acc or not token:
        raise RuntimeError('CF_ACCOUNT_ID and CF_API_TOKEN secrets are required')
    url = f'https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{model}'
    prompt = f'''Write an ORIGINAL, family-friendly visual stickman comedy for a 20–30 second vertical YouTube Short.
TOPIC: {topic}
Return ONLY valid JSON with exactly this structure:
{{"title":"short catchy title","scenes":[{{"prompt":"full visual scene description", "narration":"one short spoken sentence"}}]}}
Rules:
- Exactly 5 scenes, clear beginning / escalating mishaps / funny payoff.
- Visually consistent single white-headed stickman and a consistent location across scenes.
- Each scene's prompt describes visible actions, subject positions, background details, facial expressions and 2D cartoon lighting. Avoid text inside illustrations.
- Narration is easy English, approximately 7–14 words per scene.
- No quotes inside string values unless escaped. No markdown, no commentary.
- No copyrighted characters, trademarks, identifiable real people, dangerous activities, or misleading facts.'''
    body = json.dumps({'messages': [
        {'role': 'system', 'content': 'You are a storyboard writer. Respond with a single valid JSON object and no extra text.'},
        {'role': 'user', 'content': prompt},
    ], 'max_tokens': 1300, 'temperature': 0.75}).encode('utf-8')
    req = urllib.request.Request(url, body, {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        details = error.read(600).decode('utf-8', 'replace')
        raise RuntimeError(f'Cloudflare text model HTTP {error.code}: {details}') from error
    if payload.get('success') is False:
        raise RuntimeError(f'Cloudflare text model error: {payload.get("errors")}')
    result = payload.get('result', {})
    content = result.get('response') if isinstance(result, dict) else None
    if not content and isinstance(result, dict):
        choices = result.get('choices') or []
        if choices:
            content = (choices[0].get('message') or {}).get('content') or choices[0].get('text')
    if not content:
        raise ValueError('Text model returned no response field')
    return extract_json(content)


def validate_and_build(raw, topic):
    if not isinstance(raw, dict) or not isinstance(raw.get('scenes'), list) or len(raw['scenes']) != 5:
        raise ValueError('AI must provide exactly five scenes')
    segments = []
    for i, scene in enumerate(raw['scenes']):
        if not isinstance(scene, dict):
            raise ValueError(f'Scene {i + 1} must be an object')
        visual, narration = scene.get('prompt'), scene.get('narration')
        if not isinstance(visual, str) or not 30 <= len(visual.strip()) <= 950:
            raise ValueError(f'Scene {i + 1} requires a 30–950 character visual prompt')
        if not isinstance(narration, str) or not 10 <= len(narration.strip()) <= 250:
            raise ValueError(f'Scene {i + 1} requires a short narration sentence')
        segments.append({
            'type': 'still', 'path': f'scene-{i + 1:02d}.png',
            'prompt': visual.strip(), 'move': MOVES[i], 'transition': TRANSITIONS[i],
            'min': 3.0, 'pad': 0.50, 'narration': narration.strip(),
        })
    title = str(raw.get('title') or topic).strip()[:90]
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:45] or 'stickman-short'
    suffix = os.environ.get('GITHUB_RUN_ID') or dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')
    return {
        'slug': f'{slug}-{suffix}', 'aspect': '9:16', 'voice': 'am_puck',
        'speed': 1.05, 'music_gain': 0.32, 'segments': segments,
    }


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit('Usage: python auto_spec.py jobs/auto/spec.json [topic]')
    output = Path(sys.argv[1])
    topic = (sys.argv[2] if len(sys.argv) == 3 else os.environ.get('SHORTS_TOPIC', '')).strip()
    if not topic:
        rotation = dt.datetime.now(dt.timezone.utc).date().toordinal()
        topic = TOPICS[rotation % len(TOPICS)]
    raw = call_ai(topic)
    spec = validate_and_build(raw, topic)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Auto-generated spec: {output} ({len(spec["segments"])} scenes)')
    print('Topic:', topic)
    print('Slug:', spec['slug'])


if __name__ == '__main__':
    main()
