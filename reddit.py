import os
import sys
import calendar
import datetime
import requests
import praw
from os import environ
from moviepy.editor import VideoFileClip, concatenate_videoclips
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
CLIENT_ID_YOUTUBE = environ.get("CLIENT_ID")
CLIENT_SECRET_YOUTUBE = environ.get("CLIENT_SECRET")
REFRESH_TOKEN = environ.get("REFRESH_TOKEN")
timestamp = datetime.now().strftime("%Y%m%d")
timestampFile = datetime.now().strftime("%H%M%S")
# Personal Reddit Info (ensure USER_AGENT is provided)
client_id = "cteX2WuueE4oRMIyeMagAQ"
client_secret = "7pYFeV-hJyLVhlq8in-aEKnna930Ag"
user_agent = "MyRedditApp/0.1 by Current_Platform990"  # Set a valid user agent!
username = "Current_Platform990"
password = "eDwArD!@#1"

folder = os.getcwd()

# Create Reddit instance
try:
    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        username=username,
        password=password
    )
    print("Reddit instance created successfully.", flush=True)
except Exception as e:
    print("Error creating Reddit instance:", e, flush=True)
    sys.exit(1)

# Determine the current weekday
today = datetime.datetime.now()
weekday = calendar.weekday(today.year, today.month, today.day)
print("Weekday (0=Mon, 6=Sun):", weekday, flush=True)

# Select subreddit and post type based on weekday
if weekday in [0, 4]:
    subred = reddit.subreddit("ClashRoyale")
    new = subred.hot(limit=50)
    game = "Clash Royale"
elif weekday in [1, 5]:
    subred = reddit.subreddit("MinecraftMemes")
    new = subred.hot(limit=50)
    game = "Minecraft"
elif weekday == 2:
    subred = reddit.subreddit("WarzoneClips")
    new = subred.new(limit=50)
    game = "Warzone"
elif weekday == 3:
    subred = reddit.subreddit("GrandTheftAutoV")
    new = subred.new(limit=50)
    game = "GTA"
elif weekday == 6:
    subred = reddit.subreddit("ValorantMemes")
    new = subred.hot(limit=70)
    game = "Valorant"
else:
    print("Invalid weekday value.", flush=True)
    sys.exit(1)

# Read the video count from count.txt
count_file = os.path.join(folder, "count.txt")
try:
    with open(count_file, "r") as f:
        count = int(f.read().strip())
    print("Video count:", count, flush=True)
except Exception as e:
    print("Error reading count.txt:", e, flush=True)
    count = 0

# Create today's folder for downloads
todayfolder = os.path.join(
    folder, "memes", today.strftime('%Y'), today.strftime('%m'), today.strftime('%d')
)
try:
    os.makedirs(todayfolder, exist_ok=True)
    print("Created/verified download folder:", todayfolder, flush=True)
except Exception as e:
    print("Error creating folder:", e, flush=True)
    sys.exit(1)

# Check if today's video already exists
output_file = os.path.join(folder, "output", f"output{today.strftime('%Y-%m-%d')}.mp4")
if os.path.exists(output_file):
    print("Video already created for today. Exiting.", flush=True)
    sys.exit(0)

# Download videos using PRAW's video URL attribute
videos = []
for post in new:
    print("Post title:", post.title, flush=True)
    print("Post URL:", post.url, flush=True)
    
    # Process only video posts using PRAW's built-in attributes
    if post.is_video and post.media and 'reddit_video' in post.media:
        video_url = post.media['reddit_video'].get('fallback_url')
        if video_url:
            print("Video URL:", video_url, flush=True)
            try:
                reqDWN = requests.get(video_url)
                video_filename = os.path.join(
                    todayfolder, f"{datetime.datetime.now().strftime('%H-%M-%S')}.mp4"
                )
                with open(video_filename, "wb") as f:
                    f.write(reqDWN.content)
                videos.append(video_filename)
            except Exception as e:
                print("Error downloading video:", e, flush=True)
        else:
            print("No fallback_url available; skipping post.", flush=True)
    else:
        print("Not a video post; skipping.", flush=True)

# Merge video clips if any were downloaded
if not videos:
    print("No valid clips downloaded. Exiting.", flush=True)
    sys.exit(1)

clips = []
for video_file in videos:
    try:
        print("Processing file:", video_file, flush=True)
        clip = VideoFileClip(video_file)
        clips.append(clip)
    except Exception as e:
        print("Error with file:", video_file, "Error:", e, flush=True)
        os.remove(video_file)
        print("Removed corrupt file:", video_file, flush=True)

if not clips:
    print("No valid clips after processing. Exiting.", flush=True)
    sys.exit(1)

print("Merging clips...", flush=True)


def get_authenticated_service():
    try:
        credentials = Credentials(
            None,
            refresh_token=REFRESH_TOKEN,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=CLIENT_ID_YOUTUBE,
            client_secret=CLIENT_SECRET_YOUTUBE
        )
        credentials.refresh(Request())
        return build('youtube', 'v3', credentials=credentials)
    except Exception as e:
        print(f"Error authenticating YouTube service: {e}")
        return None

def upload_video_to_youtube(video_file_path, title, description, tags, category_id, privacy_status):
    try:
        youtube = get_authenticated_service()
        if not youtube:
            raise ValueError("Failed to get YouTube authenticated service")

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': privacy_status
            }
        }

        media = MediaFileUpload(video_file_path, chunksize=-1, resumable=True)

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = request.execute()
        print(f"Video uploaded to YouTube: {response['id']}")
        return response
    except Exception as e:
        print(f"Error uploading video to YouTube: {e}")
        base, ext = os.path.splitext(video_file_path)
        new_file_path = f"{timestampFile}_{base}_retry{ext}"

        # Ensure we don't overwrite an existing file
        counter = 1
        while os.path.exists(new_file_path):
            new_file_path = f"{timestampFile}_{base}_retry{counter}{ext}"
            counter += 1

        os.rename(video_file_path, new_file_path)
        print(f"Renamed file to: {new_file_path}")
        
        return {"error": str(e)}

final_clip = concatenate_videoclips(clips, method="compose")
output_folder = os.path.join(folder, "output")
os.makedirs(output_folder, exist_ok=True)
final_output = os.path.join(output_folder, f"output{today.strftime('%Y-%m-%d')}.mp4")
final_clip.write_videofile(final_output)

# Prepare YouTube upload details (this part is not implemented)
vidtitle = f"Memes/Funny Clips {game} #{count}"
description = f"Automated Memes/Funny Clips video #{count}\n\nContact Me: multiculturaltoolbox.com"
print("Video Title:", vidtitle, flush=True)
print("Description:", description, flush=True)

youtube_tags = [game, 'facts', 'https://edwardize.blogspot.com/', "http://multiculturaltoolbox.com/", "#{game}", "#Funny"]
youtube_category_id = '22'  # YouTube category ID
youtube_privacy_status = 'public'
response = upload_video_to_youtube(final_output, vidtitle, description, youtube_tags, youtube_category_id, youtube_privacy_status)

# Update the video count
with open(count_file, "w") as f:
    f.write(str(count + 1))
print("Updated video count to:", count + 1, flush=True)

print("done", flush=True)
