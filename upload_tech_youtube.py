#!/usr/bin/env python3
"""Upload a generated Technology Then vs Now MP4 with Google OAuth refresh token."""
import argparse
import json
import os
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--video', default='output.mp4')
    p.add_argument('--metadata', default='tech_metadata.json')
    p.add_argument('--privacy', choices=['public', 'unlisted', 'private'], default='public')
    args = p.parse_args()
    video = Path(args.video)
    if not video.exists() or video.stat().st_size < 10000:
        raise SystemExit(f'Missing or empty video: {video}')
    meta = json.loads(Path(args.metadata).read_text(encoding='utf-8'))
    streams = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=width,height', '-of', 'json', str(video)
    ], text=True)).get('streams', [])
    if not streams or streams[0]['height'] <= streams[0]['width']:
        raise SystemExit('Video is not in portrait format')
    keys = ('YT_CLIENT_ID', 'YT_CLIENT_SECRET', 'YT_REFRESH_TOKEN')
    missing = [key for key in keys if not os.getenv(key)]
    if missing:
        raise SystemExit('Missing GitHub Actions secrets: ' + ', '.join(missing))

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        None, refresh_token=os.environ['YT_REFRESH_TOKEN'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=os.environ['YT_CLIENT_ID'],
        client_secret=os.environ['YT_CLIENT_SECRET'],
        scopes=['https://www.googleapis.com/auth/youtube.upload'],
    )
    creds.refresh(Request())
    youtube = build('youtube', 'v3', credentials=creds, cache_discovery=False)
    body = {
        'snippet': {
            'title': meta['title'][:100],
            'description': meta['description'][:4900],
            'tags': ['Tech History','Technology','Then vs Now','Evolution','YouTube Shorts'],
            'categoryId': '28',
            'defaultLanguage':'en',
        },
        'status': {'privacyStatus':args.privacy, 'selfDeclaredMadeForKids': False},
    }
    media = MediaFileUpload(str(video), mimetype='video/mp4', resumable=True,
                            chunksize=8*1024*1024)
    request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
    response = None
    while response is None:
        progress, response = request.next_chunk()
        if progress:
            print('Upload progress:',f'{progress.progress()*100:.1f}%',flush=True)
    if not response or 'id' not in response:
        raise SystemExit('YouTube did not confirm an uploaded video ID')
    url='https://www.youtube.com/watch?v='+response['id']
    result={'video_id':response['id'],'url':url,'requested_privacy':args.privacy,
            'topic':meta['topic'],'title':meta['title']}
    Path('youtube-upload.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Uploaded:',url)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
            f.write(f'### Technology Short published\n\n[{meta["title"]}]({url})\n\nRequested visibility: **{args.privacy}**\n')

if __name__=='__main__':
    main()
