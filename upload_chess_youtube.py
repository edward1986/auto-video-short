#!/usr/bin/env python3
"""Publish the completed chess Short to YouTube using repository OAuth secrets."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', default='output.mp4')
    parser.add_argument('--pgn', default='random_game.pgn')
    parser.add_argument('--privacy', choices=('public', 'unlisted', 'private'), default='public')
    args = parser.parse_args()

    video = Path(args.video)
    if not video.is_file() or video.stat().st_size < 10000:
        raise SystemExit(f'Video missing or empty: {video}')
    stream_info = subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'json', str(video)
    ], text=True)
    streams = json.loads(stream_info).get('streams', [])
    if not streams or streams[0]['height'] <= streams[0]['width']:
        raise SystemExit('Expected a vertical chess Short')

    required = ['YT_CLIENT_ID', 'YT_CLIENT_SECRET', 'YT_REFRESH_TOKEN']
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise SystemExit('Missing GitHub secrets: ' + ', '.join(missing))

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    title = os.getenv('YT_CHESS_TITLE', 'Stockfish vs Stockfish ♟️ Engine Battle #Shorts').strip()[:100]
    pgn_excerpt = Path(args.pgn).read_text(encoding='utf-8')[:1200] if Path(args.pgn).exists() else ''
    description = (
        'Watch Stockfish play both sides in this chess engine battle! '
        'Every move comes with original sound effects and background music.\n\n'
        'Game PGN (excerpt):\n' + pgn_excerpt + '\n\n#Shorts #Chess #Stockfish'
    )[:4900]

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
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['Chess', 'Stockfish', 'Chess Shorts', 'AI Chess'],
            'categoryId': '20',
        },
        'status': {'privacyStatus': args.privacy, 'selfDeclaredMadeForKids': False},
    }
    media = MediaFileUpload(str(video), mimetype='video/mp4', resumable=True,
                            chunksize=8 * 1024 * 1024)
    request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
    response = None
    while response is None:
        progress, response = request.next_chunk()
        if progress:
            print(f'Upload progress: {progress.progress()*100:.1f}%', flush=True)

    watch_url = f'https://www.youtube.com/watch?v={response["id"]}'
    result = {'video_id': response['id'], 'url': watch_url, 'requested_privacy': args.privacy}
    Path('youtube-upload.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('YouTube upload completed:', watch_url)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(f'### Chess Short uploaded\n\n[{title}]({watch_url})\n\nRequested visibility: **{args.privacy}**\n')


if __name__ == '__main__':
    main()
