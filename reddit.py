import os
import sys
import calendar
import datetime
import requests
import praw
from moviepy.editor import VideoFileClip, concatenate_videoclips

print("reddit", flush=True)

# Personal Reddit Info (ensure USER_AGENT is provided)
client_id = "cteX2WuueE4oRMIyeMagAQ"
client_secret = "7pYFeV-hJyLVhlq8in-aEKnna930Ag"
user_agent = "MyRedditApp/0.1 by Current_Platform990"  # provide a valid user agent!
username = "Current_Platform990"
password = "eDwArD!@#1"

folder = os.getcwd()

# Create Reddit instance and log the current user (if possible)
try:
    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        username=username,
        password=password
    )
    print("Reddit instance created successfully.", flush=True)
    # Uncomment the following line to check your logged-in user (be cautious printing sensitive info)
    # print("Logged in as:", reddit.user.me(), flush=True)
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

# Download videos from posts
videos = []
for post in new:
    print("Post title:", post.title, flush=True)
    print("Post URL:", post.url, flush=True)
    url_parts = post.url.split(".")
    if url_parts[-1].lower() not in ["gif", "png", "jpg"]:
        try:
            req = requests.get(post.url)
            content = req.content
            parts = content.split(b'canonicalUrl":"')
            if len(parts) < 2:
                print("No canonicalUrl found; skipping post.", flush=True)
                continue
            postURL = parts[1].split(b'"')[0].decode("utf-8")
            downloadURL = (
                "https://sd.redditsave.com/download.php?permalink=" + postURL +
                "&video_url=" + post.url + "/DASH_720.mp4?source=fallback" +
                "&audio_url=" + post.url + "/DASH_audio.mp4?source=fallback"
            )
            print("Download URL:", downloadURL, flush=True)
            reqDWN = requests.get(downloadURL)
            video_filename = os.path.join(
                todayfolder, f"{datetime.datetime.now().strftime('%H-%M-%S')}.mp4"
            )
            with open(video_filename, "wb") as f:
                f.write(reqDWN.content)
            videos.append(video_filename)
        except Exception as e:
            print("Error downloading video:", e, flush=True)
    else:
        print("Skipped image post.", flush=True)

# Merge video clips
clips = []
memes_files = os.listdir(todayfolder)
for meme in memes_files:
    meme_path = os.path.join(todayfolder, meme)
    try:
        print("Processing file:", meme_path, flush=True)
        clip = VideoFileClip(meme_path)
        clips.append(clip)
    except Exception as e:
        print("Error with file:", meme_path, "Error:", e, flush=True)
        os.remove(meme_path)
        print("Removed corrupt file:", meme_path, flush=True)

if not clips:
    print("No valid clips downloaded. Exiting.", flush=True)
    sys.exit(1)

print("Merging clips...", flush=True)
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

# Update the video count
with open(count_file, "w") as f:
    f.write(str(count + 1))
print("Updated video count to:", count + 1, flush=True)

print("done", flush=True)
