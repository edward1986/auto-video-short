import os
import sys
import calendar
import requests
import praw
from datetime import datetime
from os import environ
from dotenv import load_dotenv
from PIL import Image

# Monkeypatch for MoviePy 1.0.3 compatibility with Pillow 10+
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import (
    VideoFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
)
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

from videoProcess.Styling import (
    get_text_clip,
    create_noise_overlay,
    create_gradient_glow,
    create_vignette,
    apply_zoom,
    apply_kinetic_pop,
    apply_slide_in,
    darken_clip,
    create_flash_transition,
    create_end_card,
)

load_dotenv(".env")
CLIENT_ID_YOUTUBE = environ.get("CLIENT_ID")
CLIENT_SECRET_YOUTUBE = environ.get("CLIENT_SECRET")
REFRESH_TOKEN = environ.get("REFRESH_TOKEN")
timestamp = datetime.now().strftime("%Y%m%d")
timestampFile = datetime.now().strftime("%H%M%S")

# Personal Reddit Info
client_id = environ.get("REDDIT_CLIENT_ID")
client_secret = environ.get("REDDIT_CLIENT_SECRET")
user_agent = environ.get("REDDIT_USER_AGENT")
username = environ.get("REDDIT_USERNAME")
password = environ.get("REDDIT_PASSWORD")

folder = os.getcwd()

# Create Reddit instance
try:
    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        username=username,
        password=password,
    )
    print("Reddit instance created successfully.", flush=True)
except Exception as e:
    print("Error creating Reddit instance:", e, flush=True)
    sys.exit(1)

# Determine the current weekday
today = datetime.now()
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
    folder, "memes", today.strftime("%Y"), today.strftime("%m"), today.strftime("%d")
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

# Download videos and retrieve top comment
video_items = []
for post in new:
    if len(video_items) >= 5:  # Limit to 5 clips for performance
        break
    print("Post title:", post.title, flush=True)

    # Retrieve top comment
    try:
        post.comments.replace_more(limit=0)
        if post.comments:
            top_comment = post.comments[0].body
        else:
            top_comment = "No comments available."
    except Exception:
        top_comment = "Error retrieving comment."

    # Process only video posts
    if post.is_video and post.media and "reddit_video" in post.media:
        video_url = post.media["reddit_video"].get("fallback_url")
        if video_url:
            try:
                reqDWN = requests.get(video_url)
                video_filename = os.path.join(
                    todayfolder, f"{datetime.now().strftime('%H-%M-%S')}.mp4"
                )
                with open(video_filename, "wb") as f:
                    f.write(reqDWN.content)
                video_items.append((video_filename, top_comment, post.title))
            except Exception as e:
                print("Error downloading video:", e, flush=True)

# Merge video clips
if not video_items:
    print("No valid clips downloaded. Exiting.", flush=True)
    sys.exit(1)

resolution = (1080, 1920)
clips = []

for video_file, comment, title in video_items:
    try:
        print("Processing file:", video_file, flush=True)
        # target_resolution offloads resizing to FFmpeg during decoding
        clip = VideoFileClip(video_file, target_resolution=(1920, None)).resize(
            resolution
        )

        # 2026 Style: Darken and Zoom
        clip = darken_clip(clip, factor=0.45)
        clip = apply_zoom(clip, clip.duration)

        # 2026 Style: Kinetic Typography for Comment
        # Using a subset of build_modern_captions logic for a single block
        comment_clip = get_text_clip(
            comment.upper(),
            fontsize=70,
            color="white",
            stroke_color="black",
            stroke_width=3,
            size=(900, None),
            align="center",
            box_color=(0, 0, 0, 128),
            box_padding=20,
        ).set_duration(clip.duration)

        # Snappy entrance
        comment_clip = apply_slide_in(
            comment_clip, duration=0.4, direction="bottom", final_pos=("center", 0.7)
        )
        comment_clip = apply_kinetic_pop(comment_clip, duration=0.2, scale=1.1)

        # 2026 Overlays (Grain, Glow, Vignette)
        noise = create_noise_overlay(resolution, clip.duration, opacity=0.1)
        glow = create_gradient_glow(resolution, clip.duration, opacity=0.15)
        vignette = create_vignette(resolution, clip.duration, opacity=0.4)

        # Flash at the start of each clip
        flash = create_flash_transition(resolution, duration=0.2)

        composite = CompositeVideoClip(
            [clip, glow, noise, vignette, comment_clip, flash],
            size=resolution,
            use_bgclip=True,
        )
        clips.append(composite)
    except Exception as e:
        print("Error with file:", video_file, "Error:", e, flush=True)
        if os.path.exists(video_file):
            os.remove(video_file)

if not clips:
    print("No valid clips after processing. Exiting.", flush=True)
    sys.exit(1)

print("Merging clips...", flush=True)

# 2026 Style Intro
intro_text = get_text_clip(
    "REDDIT MADNESS",
    fontsize=150,
    color="white",
    stroke_color="black",
    stroke_width=5,
    rotation=-3,
).set_duration(2)
intro_text = apply_kinetic_pop(intro_text, duration=0.5, scale=1.5)
intro_bg = CompositeVideoClip(
    [
        create_gradient_glow(resolution, 2, color=(0, 255, 0), opacity=0.3),
        create_noise_overlay(resolution, 2, opacity=0.15),
        intro_text.set_position("center"),
    ],
    size=resolution,
)

# 2026 Style Outro
outro_clip = create_end_card(resolution, text="LIKE & SUBSCRIBE")

final_clip = concatenate_videoclips(
    [intro_bg] + clips + [outro_clip], method="compose", padding=-0.2
)
output_folder = os.path.join(folder, "output")
os.makedirs(output_folder, exist_ok=True)
final_output = os.path.join(output_folder, f"output{today.strftime('%Y-%m-%d')}.mp4")

threads = os.cpu_count() or 4
final_clip.write_videofile(
    final_output, codec="libx264", audio_codec="aac", threads=threads, preset="fast"
)


def get_authenticated_service():
    try:
        credentials = Credentials(
            None,
            refresh_token=REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID_YOUTUBE,
            client_secret=CLIENT_SECRET_YOUTUBE,
        )
        credentials.refresh(Request())
        return build("youtube", "v3", credentials=credentials)
    except Exception as e:
        print(f"Error authenticating YouTube service: {e}")
        return None


def upload_video_to_youtube(
    video_file_path, title, description, tags, category_id, privacy_status
):
    try:
        youtube = get_authenticated_service()
        if not youtube:
            raise ValueError("Failed to get YouTube authenticated service")

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {"privacyStatus": privacy_status},
        }

        media = MediaFileUpload(video_file_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        response = request.execute()
        print(f"Video uploaded to YouTube: {response['id']}")
        return response
    except Exception as e:
        print(f"Error uploading video to YouTube: {e}")
        return {"error": str(e)}


# Prepare YouTube upload details
vidtitle = f"Reddit {game} Moments #{count}"
description = f"Automated {game} highlights from Reddit.\n\n#reddit #{game.replace(' ', '')} #memes"
youtube_tags = [game, "reddit", "memes", "#shorts"]
youtube_category_id = "22"
youtube_privacy_status = "public"

response = upload_video_to_youtube(
    final_output,
    vidtitle,
    description,
    youtube_tags,
    youtube_category_id,
    youtube_privacy_status,
)

# Update the video count
with open(count_file, "w") as f:
    f.write(str(count + 1))
print("Updated video count to:", count + 1, flush=True)

print("done", flush=True)
