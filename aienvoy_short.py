#!/usr/bin/env python3
"""Generate one 9:16 AI short with AiEnvoy's published story-generation API.

Requires AI_ENVOY_KEY. Async responses need a status URL from the response, or
AI_ENVOY_STATUS_URL_TEMPLATE (containing {task_id}) obtained from AiEnvoy docs.
No unverified task polling endpoint is assumed.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urljoin, urlparse

import requests

API_BASE = 'https://api.aienvoy.dev'
GENERATE_URL = API_BASE + '/api/v1/videos/generate'
TERMINAL_SUCCESS = {'completed', 'complete', 'succeeded', 'success', 'finished', 'done'}
TERMINAL_FAILURE = {'failed', 'failure', 'error', 'cancelled', 'canceled', 'rejected'}


def obj_get(obj, *keys):
    """Return the first available field from nested data/result objects."""
    if not isinstance(obj, dict):
        return None
    values = [obj]
    for name in ('data', 'result', 'output'):
        if isinstance(obj.get(name), dict):
            values.append(obj[name])
    for container in values:
        for key in keys:
            if container.get(key) is not None:
                return container[key]
    return None


def api_response(response):
    if not response.ok:
        raise RuntimeError(f'AiEnvoy HTTP {response.status_code}: {response.text[:800]}')
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError('AiEnvoy returned non-JSON API response') from exc
    if data.get('success') is False:
        raise RuntimeError('AiEnvoy rejected request: ' + json.dumps(data.get('errors', data))[:800])
    return data


def video_url(data):
    for key in ('video_url', 'download_url', 'result_url', 'output_url', 'url'):
        found = obj_get(data, key)
        if isinstance(found, str) and found.startswith('https://'):
            return found
    # Some task APIs return a nested video object.
    found = obj_get(data, 'video')
    if isinstance(found, dict):
        for key in ('url', 'download_url'):
            val = found.get(key)
            if isinstance(val, str) and val.startswith('https://'):
                return val
    return None


def create(args, session):
    payload = {
        'topic': args.topic,
        'style': args.style,
        'duration': args.duration,
        'voice': args.voice,
        'music_mood': args.music_mood,
        'aspect_ratio': '9:16',
    }
    if args.dry_run:
        print(json.dumps({'endpoint': GENERATE_URL, 'payload': payload}, indent=2))
        return None
    data = api_response(session.post(GENERATE_URL, json=payload, timeout=60))
    Path(args.output_dir, 'aienvoy-create-response.json').write_text(json.dumps(data, indent=2))
    return data


def poll(data, args, session):
    task = obj_get(data, 'task_id', 'id')
    direct = video_url(data)
    if direct:
        return direct
    if not task:
        raise RuntimeError('No video URL or task ID returned. Inspect aienvoy-create-response.json.')
    task = str(task)
    # The provider documentation publicly establishes async polling, but not its exact route.
    # Prefer an API-supplied status URL. Otherwise require the exact route from your account docs.
    status_url = obj_get(data, 'status_url', 'poll_url', 'task_url')
    if isinstance(status_url, str) and status_url.startswith('/'):
        status_url = urljoin(API_BASE, status_url)
    if not status_url:
        template = os.getenv('AI_ENVOY_STATUS_URL_TEMPLATE', '').strip()
        if not template or '{task_id}' not in template:
            raise RuntimeError(
                f'AiEnvoy started task {task}, but its public docs did not establish the polling endpoint. '
                'Set AI_ENVOY_STATUS_URL_TEMPLATE to the documented HTTPS task-status URL with {task_id}, '
                'or provide an API response that contains status_url.'
            )
        status_url = template.replace('{task_id}', task)
    if not isinstance(status_url, str) or not status_url.startswith('https://'):
        raise RuntimeError('Task-status URL must use HTTPS')
    if urlparse(status_url).hostname != urlparse(API_BASE).hostname:
        raise RuntimeError('Task-status URL must use the official AiEnvoy API host')
    deadline = time.monotonic() + args.timeout_minutes * 60
    while time.monotonic() < deadline:
        result = api_response(session.get(status_url, timeout=30))
        status = str(obj_get(result, 'status', 'state') or '').lower()
        found = video_url(result)
        if status in TERMINAL_FAILURE:
            raise RuntimeError('AiEnvoy task failed: ' + json.dumps(result)[:800])
        if found and (status in TERMINAL_SUCCESS or not status):
            return found
        print(f'AiEnvoy task {task}: {status or "processing"}', flush=True)
        time.sleep(args.poll_seconds)
    raise TimeoutError(f'AiEnvoy task {task} timed out after {args.timeout_minutes} minutes')


def download(url, target, session):
    if urlparse(url).scheme != 'https':
        raise RuntimeError('Refusing a non-HTTPS output URL')
    # Video URLs may be hosted by the provider on a signed CDN.
    with session.get(url, stream=True, timeout=(30, 180), allow_redirects=True) as resp:
        resp.raise_for_status()
        with open(target, 'wb') as f:
            for chunk in resp.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
    if target.stat().st_size < 10000:
        raise RuntimeError(f'Downloaded media is too small ({target.stat().st_size} bytes)')


def normalize(raw, final):
    # Scale to contain, then blurred/black matte bars. Never squash or stretch.
    cmd = [
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(raw),
        '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,'
               'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30,format=yuv420p',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '21',
        '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(final)
    ]
    subprocess.run(cmd, check=True)
    info = subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'json', str(final)
    ], text=True)
    stream = json.loads(info)['streams'][0]
    if (stream['width'], stream['height']) != (1080, 1920):
        raise RuntimeError('Output failed 9:16 validation')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--topic', default='A funny stickman tries to make coffee, but a mischievous robot keeps changing the order; family-friendly visual comedy, surprising ending')
    ap.add_argument('--style', default='colorful 2D cartoon, funny stickman animation, family-friendly')
    ap.add_argument('--duration', default='60s')
    ap.add_argument('--voice', default='narrative_male')
    ap.add_argument('--music-mood', default='playful')
    ap.add_argument('--output-dir', default='render_output')
    ap.add_argument('--timeout-minutes', type=int, default=50)
    ap.add_argument('--poll-seconds', type=int, default=15)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    key = os.getenv('AI_ENVOY_KEY', '').strip()
    if not key and not args.dry_run:
        raise SystemExit('Missing AI_ENVOY_KEY environment variable')
    session = requests.Session()
    session.headers.update({'X-API-Key': key, 'Accept': 'application/json'})
    data = create(args, session)
    if args.dry_run:
        return
    url = poll(data, args, session)
    raw, final = folder / 'aienvoy-original.mp4', folder / 'aienvoy-short.mp4'
    # Do not send API key to the download host; signed URLs should be self-contained.
    download(url, raw, requests.Session())
    normalize(raw, final)
    metadata = {'title': 'Stickman Comedy Short #Shorts', 'description': args.topic,
                'slug': 'aienvoy-short', 'segments': [{'narration': args.topic}]}
    (folder / 'metadata.json').write_text(json.dumps(metadata, indent=2))
    print('MP4:', final, flush=True)


if __name__ == '__main__':
    main()
