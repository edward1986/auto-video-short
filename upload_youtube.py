#!/usr/bin/env python3
"""Publish a successfully rendered Short to YouTube using OAuth secrets.
Usage: python upload_youtube.py job/spec.json render_output/video.mp4
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python upload_youtube.py spec.json output.mp4')
    spec = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    video = Path(sys.argv[2])
    if not video.is_file() or video.stat().st_size < 10000:
        raise SystemExit(f'Video missing or too small: {video}')

    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=codec_name,width,height', '-of', 'json', str(video)],
        capture_output=True, text=True, check=True,
    )
    streams = json.loads(result.stdout).get('streams', [])
    if not streams:
        raise SystemExit('No video stream found')
    video_stream = streams[0]
    if (video_stream['width'], video_stream['height']) != (1080, 1920):
        raise SystemExit('Refusing to upload: expected vertical 1080x1920 video')

    required = ('YT_CLIENT_ID', 'YT_CLIENT_SECRET', 'YT_REFRESH_TOKEN')
    missing = [name for name in required if not os.environ.get(name, '').strip()]
    if missing:
        raise SystemExit('Missing GitHub Actions secrets: ' + ', '.join(missing))

    privacy = os.getenv('YT_PRIVACY', 'public').lower().strip()
    if privacy not in ('public', 'private', 'unlisted'):
        raise SystemExit('YT_PRIVACY must be public, private, or unlisted')

    # The auto-generated comedy spec has a slug and narration in its scenes.
    title = spec.get('title') or spec.get('youtube_title') or spec.get('slug', 'Animated Short')
    title = re.sub(r'-\d{8,}$', '', str(title)).replace('-', ' ').strip()
    title = title[:85] + ' #Shorts'
    narration = []
    for segment in spec.get('segments', []):
        lines = segment.get('narration') or []
        narration.extend([lines] if isinstance(lines, str) else lines)
    description = (spec.get('description') or ' '.join(narration)[:3500]).strip()
    description = description + '\n\n#Shorts #Animation #Comedy'

    credentials = Credentials(
        None,
        refresh_token=os.environ['YT_REFRESH_TOKEN'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=os.environ['YT_CLIENT_ID'],
        client_secret=os.environ['YT_CLIENT_SECRET'],
        scopes=['https://www.googleapis.com/auth/youtube.upload'],
    )
    credentials.refresh(Request())
    youtube = build('youtube', 'v3', credentials=credentials, cache_discovery=False)
    media = MediaFileUpload(str(video), mimetype='video/mp4', resumable=True, chunksize=8*1024*1024)
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'categoryId': '23',
            'tags': ['Shorts', 'Animation', 'Comedy'],
        },
        'status': {
            'privacyStatus': privacy,
            'selfDeclaredMadeForKids': False,
        },
    }
    request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
    response = None
    while response is None:
        progress, response = request.next_chunk()
        if progress:
            print(f'YouTube upload {progress.progress() * 100:.0f}%', flush=True)
    output = {'id': response['id'], 'url': f'https://www.youtube.com/watch?v={response["id"]}', 'privacy': privacy}
    Path('youtube-upload.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print('Published:', output['url'], 'visibility:', privacy)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(f'### YouTube upload\n\n[{title}]({output["url"]}) — **{privacy}**\n')


if __name__ == '__main__':
    main()
