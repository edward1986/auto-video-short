#!/usr/bin/env python3
"""Upload validated Shorts with OAuth refresh token from GitHub Secrets."""
import json
import os
from pathlib import Path
import subprocess
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

if len(sys.argv)!=3:
    sys.exit('Usage: python upload_youtube.py spec.json rendered-video.mp4')
spec=json.loads(Path(sys.argv[1]).read_text())
video=Path(sys.argv[2])
if not video.is_file() or video.stat().st_size < 10000:
    sys.exit('Video missing or unexpectedly small')
probe=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',str(video)])
stream=json.loads(probe)['streams'][0]
if (int(stream['width']),int(stream['height']))!=(1080,1920):
    sys.exit('Refusing upload: video is not 1080x1920')
privacy=os.getenv('YT_PRIVACY','public').strip().lower()
if privacy not in {'public','private','unlisted'}:
    sys.exit('Invalid YT_PRIVACY')
ids=['YT_CLIENT_ID','YT_CLIENT_SECRET','YT_REFRESH_TOKEN']
missing=[name for name in ids if not os.getenv(name)]
if missing:
    sys.exit('Missing GitHub secrets: '+', '.join(missing))
credentials=Credentials(None,refresh_token=os.environ['YT_REFRESH_TOKEN'],
    token_uri='https://oauth2.googleapis.com/token',client_id=os.environ['YT_CLIENT_ID'],
    client_secret=os.environ['YT_CLIENT_SECRET'],scopes=['https://www.googleapis.com/auth/youtube.upload'])
credentials.refresh(Request())
youtube=build('youtube','v3',credentials=credentials,cache_discovery=False)
title=('Trivia Time! '+spec['question'])[:100]
description=(f"{spec['question']}\n\nAnswer: {spec['options'][spec['correct_index']]}\n"
             f"{spec['explanation']}\n\n#Shorts #Trivia #Quiz")
metadata={'snippet':{'title':title,'description':description,'tags':['Shorts','Trivia','Quiz','General Knowledge'],
          'categoryId':'27'},'status':{'privacyStatus':privacy,'selfDeclaredMadeForKids':False}}
media=MediaFileUpload(str(video),mimetype='video/mp4',resumable=True,chunksize=8*1024*1024)
request=youtube.videos().insert(part='snippet,status',body=metadata,media_body=media)
response=None
while response is None:
    status,response=request.next_chunk()
    if status:
        print(f'Uploading: {status.progress()*100:.0f}%',flush=True)
print('YouTube:',f'https://www.youtube.com/watch?v={response["id"]}','privacy:',privacy)
Path('youtube-upload.json').write_text(json.dumps({'id':response['id'],'url':f'https://www.youtube.com/watch?v={response["id"]}','privacy':privacy},indent=2))
