import os
import re
import mysql.connector
import base64
import requests
import smtplib
from os import environ
from datetime import datetime
from dotenv import load_dotenv
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip, concatenate_videoclips
from textwrap import fill, shorten
from pyfiglet import Figlet
from videoProcess.Quote import get_quote
from videoProcess.SoundCreate import make_audio
from videoProcess.VideoDownload import download_video
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
load_dotenv(".env")

WORD_URL = "https://www.merriam-webster.com/word-of-the-day"
CATFACT_URL = "https://catfact.ninja/fact"


def http_get_text(url: str, headers: Optional[dict] = None, timeout: int = 30) -> tuple[int, str]:
    req = Request(url, headers=headers or {}, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200))
            text = resp.read().decode("utf-8", errors="replace")
            return status, text
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return int(e.code), body
    except URLError as e:
        return 0, str(e)


def http_post_json(url: str, payload: dict, headers: Optional[dict] = None, timeout: int = 30) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    base_headers = {"Content-Type": "application/json"}
    if headers:
        base_headers.update(headers)

    req = Request(url, data=data, headers=base_headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200))
            text = resp.read().decode("utf-8", errors="replace")
            return status, text
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return int(e.code), body
    except URLError as e:
        return 0, str(e)


def sanitize_text(s: str) -> str:
    # Matches your sed: keep alphanum, space, and these punctuations: . , ! ? -
    return re.sub(r"[^a-zA-Z0-9 \.\,\!\?\-]", "", s)


def extract_word_of_the_day(html: str) -> Optional[str]:
    # Similar intent to grep:
    # grep -oP '(?<=<h2 class="word-header-txt">)[^<]+'
    m = re.search(r'<h2\s+class="word-header-txt"\s*>\s*([^<]+)\s*</h2>', html, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).strip()


def find_first_response_string(obj: Any) -> Optional[str]:
    # Recursively find the first non-empty string under any key named "response"
    if isinstance(obj, dict):
        if "response" in obj and isinstance(obj["response"], str) and obj["response"].strip():
            return obj["response"]
        for v in obj.values():
            found = find_first_response_string(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_first_response_string(item)
            if found:
                return found
    return None


def write_github_env(key: str, value: str) -> None:
    github_env = os.getenv("GITHUB_ENV")
    if not github_env:
        # Local run: just print
        print(f"{key}={value}")
        return
    with open(github_env, "a", encoding="utf-8") as f:
        f.write(f"{key}={value}\n")
CLIENT_ID = environ.get("CLIENT_ID")
CLIENT_SECRET = environ.get("CLIENT_SECRET")
REFRESH_TOKEN = environ.get("REFRESH_TOKEN")
AUDIO_NAME = environ.get("AUDIO_NAME", "audio.mp3.wav")
VIDEO_NAME = environ.get("VIDEO_NAME", "video.mp4")
FINAL_VIDEO = environ.get("FINAL_VIDEO", "final_video.mp4")
EMAIL_USER = environ.get("EMAIL_USER")
EMAIL_PASS = environ.get("EMAIL_PASS")
EMAIL_TO = environ.get("EMAIL_TO")
PAGE_ID = environ.get("PAGE_ID")
PAGE_ACCESS_TOKEN = environ.get("PAGE_ACCESS_TOKEN")
IG_USER_ID = environ.get("IG_USER_ID")
IG_ACCESS_TOKEN = environ.get("IG_ACCESS_TOKEN")
sanitized_blog = ""
def sanitize_input(user_input):
    # Only allow alphanumeric characters and spaces
    safe_input = re.sub(r'[^a-zA-Z0-9 ]', '', user_input)
    return safe_input
# Ensure output directory exists
timestamp = datetime.now().strftime("%Y%m%d")
timestampFile = datetime.now().strftime("%H%M%S")
output_dir = f"output_{timestamp}"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Display a title using Figlet
fig_font = Figlet(font="slant", justify="left")
print(fig_font.renderText("Auto Video Short!!!"))



cf_worker_url = "https://morning-dew-a596.ntcedge2.workers.dev"
app_api_key = os.getenv("APP_API_KEY", "").strip()

model = os.getenv("MODEL", "@cf/meta/llama-4-scout-17b-16e-instruct")
try:
    max_output_tokens = int(os.getenv("MAX_OUTPUT_TOKENS", "256"))
except ValueError:
    max_output_tokens = 256

# 1) Fetch Word of the Day
status, html = http_get_text(WORD_URL, headers={"User-Agent": "Mozilla/5.0"})
if status == 200:
    word = extract_word_of_the_day(html)
    if word:
        print(f"Word of the Day fetched successfully: {word}")
    else:
        print("Word of the Day not found in the HTML content")
        word = "word"
else:
    print(f"Failed to retrieve the Word of the Day, HTTP status: {status}")
    word = "word"

write_github_env("word", word)

# 2) Generate blog using Cloudflare AI Worker
if not cf_worker_url:
    print("Missing env var CF_WORKER_URL", file=sys.stderr)
    return 1

status, cat_json = http_get_text(CATFACT_URL, headers={"User-Agent": "Mozilla/5.0"})
if status != 200:
    print(f"Failed to fetch cat fact, HTTP status: {status}", file=sys.stderr)
    return 1

try:
    cat_fact = json.loads(cat_json).get("fact", "")
except Exception:
    print("Failed to parse cat fact JSON.", file=sys.stderr)
    return 1

sanitized_fact = sanitize_text(str(cat_fact))
prompt = f"{sanitized_fact} make a blog and use the word {word}"
print(prompt)

payload = {
    "input": prompt,
    "instructions": "Write a short blog. Use simple English. Keep it clear and natural.",
    "model": model,
    "max_output_tokens": max_output_tokens,
}

headers = {}
if app_api_key:
    headers["X-APP-KEY"] = app_api_key

status, result_text = http_post_json(cf_worker_url, payload, headers=headers)

if status == 0 or status >= 400:
    print("Cloudflare Worker raw response:", file=sys.stderr)
    print(result_text, file=sys.stderr)
    return 1

try:
    result_obj = json.loads(result_text)
except Exception:
    # Worker might already return plain text JSON-ish; still print for debugging
    print("Cloudflare Worker returned non-JSON response:", file=sys.stderr)
    print(result_text, file=sys.stderr)
    return 1

blog = find_first_response_string(result_obj)
if not blog:
    # fallback shapes
    blog = (
        (result_obj.get("result") or {}).get("response")
        if isinstance(result_obj.get("result"), dict)
        else None
    ) or result_obj.get("response")

if not blog or str(blog).strip().lower() == "null":
    print("Cloudflare Worker raw response:", file=sys.stderr)
    print(result_text, file=sys.stderr)
    return 1

sanitized_blog = sanitize_text(str(blog)).replace("\n", "").replace("\r", "")
print(sanitized_blog)




prompt = sanitized_blog
# Get a quote and save it to a variable
try:
    
    text_quote = sanitize_input(prompt)
    make_audio(text_quote, output_dir, timestampFile)
except Exception as e:
    print(f"Error fetching quote or creating audio: {e}")
    exit(1)

# Save the quote to a text file
quote_file_path = os.path.join(output_dir, "quote.txt")
try:
    with open(quote_file_path, "w") as file:
        file.write(shorten(text_quote, width=90, placeholder="..."))
    print(f"Quote saved to {quote_file_path}")
except Exception as e:
    print(f"Error saving quote to file: {e}")
    exit(1)

# Download the video clip from an API
try:
    download_video(output_dir)
except Exception as e:
    print(f"Error downloading video: {e}")
    exit(1)

# Verify that the necessary files exist
audio_path = f"{output_dir}/{timestampFile}.mp3"
video_path = f"{output_dir}/{VIDEO_NAME}"
def insert_blog_post_to_db(title, summary, content, keywords, slug, thumbnail):
    # Fetch MySQL credentials from environment variables
    mysql_host = environ.get("MYSQL_HOST")
    mysql_user = os.getenv('MYSQL_USER')
    mysql_password = os.getenv('MYSQL_PASSWORD')
    mysql_database = os.getenv('MYSQL_DATABASE')

    # Connect to the remote MySQL database
    db = mysql.connector.connect(
        host=mysql_host,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database
    )

    cursor = db.cursor()
    created_at = updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    page_sql = """
    INSERT INTO `pages` (
        `id`, `slug`, `target`, `type`, `featured_image`, 
        `tool_name`, `icon_image`, `custom_tool_link`, `post_status`, 
        `page_status`, `tool_status`, `ads_status`, `popular`, 
        `position`, `category_id`, `created_at`, `updated_at`
    ) 
    VALUES (
        NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    """
    pgSlug = re.sub(r'[^a-zA-Z0-9\s-]', '', slug.replace('The title is', '').replace('The title of this blog post is', '')).lower().strip().replace('\n', ' ').replace(' ', '-').replace('the-title-of-this-polished-and-professional-blog-post-is', "").replace('the-title-of-this-polished-and-professional-blog-post-is', "")
    page_values = (
        pgSlug , "_self", "post", thumbnail,
        None, None, None,
        1, 1,1,
        1, 1, 1,
        None, created_at, updated_at
    )

    # Execute the page insertion
    cursor.execute(page_sql, page_values)
    db.commit()

    # Get the last inserted ID for `pages`
    page_id = cursor.lastrowid
    print(f"Inserted page ID: {page_id}")

    # Insert current timestamp for created_at and updated_at
    

    # SQL query to insert the generated blog post

    sql = """
    INSERT INTO `page_translations` (
        `locale`, 
        `page_title`, 
        `robots_meta`, 
        `sitename_status`, 
        `site_name_status`, 
        `title`, 
        `subtitle`, 
        `short_description`, 
        `description`, 
        `page_id`, 
        `created_at`, 
        `updated_at`
    ) 
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        "en", title.replace('The title is', '').replace('I think your revised blog post looks great', '').replace("Here is a rewritten version of the blog post with a polished and professional tone, grammar, and readability", '').replace('The title you provided is', '').replace('Here is the polished and professional version of the blog post', '').replace("Here's the revised blog post", '').replace('The title of this blog post is', '').strip('"').replace('\n', ' '), 1, 1,
        1, title.replace('The title is', '').replace('I think your revised blog post looks great', '').replace("Here is a rewritten version of the blog post with a polished and professional tone, grammar, and readability", '').replace('The title you provided is', '').replace('Here is the polished and professional version of the blog post', '').replace("Here's the revised blog post", '').strip('"').replace('\n', ' '), title.replace('The title is', '').replace('I think your revised blog post looks great', '').replace("Here is a rewritten version of the blog post with a polished and professional tone, grammar, and readability", '').replace('The title you provided is', '').replace('Here is the polished and professional version of the blog post', '').replace("Here's the revised blog post", '').strip('"').replace('\n', ' '), title.replace('The title is', '').replace('I think your revised blog post looks great', '').replace("Here is a rewritten version of the blog post with a polished and professional tone, grammar, and readability", '').replace('The title you provided is', '').replace('Here is the polished and professional version of the blog post', '').replace("Here's the revised blog post", '').strip('"').replace('\n', ' '),
        "<p>" +content.replace('Here is the edited blog post', '').replace("Here's is the edited blog post", '').replace("Here is a rewritten version of the blog post with a polished and professional tone, grammar, and readability", '').replace("Here's the revised blog post", '').replace('Here is the revised blog post', '').replace('\n', '<br>').replace('The title is', '').replace('The title of this blog post is', '').replace('Here is a polished and professional version of the blog post', '')+ "</p>", page_id, created_at, updated_at
    )
  
    cursor.execute(sql, values)
    db.commit()

if not os.path.exists(audio_path):
    print(f"Error: Audio file {audio_path} does not exist.")
    exit(1)

if not os.path.exists(video_path):
    print(f"Error: Video file {video_path} does not exist.")
    exit(1)

# Prepare the quote text for the video
text_quote = fill(text_quote, width=30, fix_sentence_endings=True)

# Set the resolution for the final video
resolution = (1080, 1920)

# Load the audio clip
try:
    audio_clip = AudioFileClip(audio_path)
except Exception as e:
    print(f"Error loading audio clip: {e}")
    exit(1)
def shorten_text(text, max_length=30):
    if len(text) > max_length:
        return text[:max_length - 3] + '...'  # Truncate and add ellipsis
    return text

def split_text_chunks(text, max_length=90):
    words = text.split()
    chunks = []
    current_chunk = ""
    for word in words:
        if len(current_chunk) + len(word) + 1 > max_length:
            chunks.append(current_chunk)
            current_chunk = word
        else:
            current_chunk += (" " + word) if current_chunk else word
    chunks.append(current_chunk)
    return chunks

base64_video = ""
final_video_path = ""
MAX_DURATION = 59

try:
    # Load video and audio clips
    video_clip = VideoFileClip(video_path, audio=False).set_audio(audio_clip).loop(duration=audio_clip.duration).resize(resolution)
    
    # Split the quote into larger chunks if necessary
    text_chunks = split_text_chunks(text_quote, max_length=90)
    
    # Calculate the duration each chunk should last
    total_duration = min(video_clip.duration, MAX_DURATION)
    chunk_duration = total_duration / len(text_chunks)
    
    # Create text clips with semi-transparent backgrounds for each chunk
    text_clips = []
    for idx, chunk in enumerate(text_chunks):
        fact_text = (
            TextClip(chunk, color='white', fontsize=50, align='center', method='caption')
            .set_position(('center', 'center'))
            .set_duration(chunk_duration)
        )
        
        fact_text_width, fact_text_height = fact_text.size
        semi_transparent_bg = (
            ColorClip(size=(fact_text_width + 40, fact_text_height + 20), color=(0, 0, 0))
            .set_opacity(0.5)
            .set_position(('center', 'center'))
            .set_duration(chunk_duration)
        )
        
        text_clip_with_bg = CompositeVideoClip([semi_transparent_bg, fact_text])
        text_clips.append(text_clip_with_bg)
    
    final_text_clip = concatenate_videoclips(text_clips)
    final = CompositeVideoClip([video_clip, final_text_clip.set_position('center')], size=video_clip.size)
    
    # Trim the final video to 1 minute
    final = final.subclip(0, MAX_DURATION)
    
    final_video_path = f"{output_dir}/{FINAL_VIDEO}"
    final.write_videofile(final_video_path, codec="libx264")
    base64_video = video_to_base64(final_video_path)

except Exception as e:
    print(f"Error processing video: {e}")

# Convert video to base64
def video_to_base64(video_path):
    try:
        with open(video_path, "rb") as video_file:
            base64_encoded_video = base64.b64encode(video_file.read()).decode('utf-8')
        return base64_encoded_video
    except Exception as e:
        print(f"Error converting video to base64: {e}")
        return None



def send_email(subject, body, to, base64_video):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to
        msg['Subject'] = subject

        html = f"""
        <div class="video-container">
                <video controls>
                    <source src="data:video/mp4;base64,{base64_video}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
            </div>
            <p>Quote: {text_quote}</p>
        """

        msg.attach(MIMEText(html, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        text = msg.as_string()
        server.sendmail(EMAIL_USER, to, text)
        server.quit()
        print(f"Email sent to {to} with embedded video")
    except Exception as e:
        print(f"Error sending email: {e}")

send_email(
    subject=text_quote,
    body="Please find the embedded video below.",
    to=EMAIL_TO,
    base64_video=base64_video
)

def like_video(video_id, page_access_token):
    try:
        url = f"https://graph.facebook.com/v20.0/{video_id}/likes"
        payload = {
            "access_token": page_access_token
        }
        response = requests.post(url, data=payload)
        response_data = response.json()
        return response_data
    except Exception as e:
        print(f"Error liking video: {e}")
        return None

def comment_on_video(video_id, page_access_token, comment_message):
    try:
        url = f"https://graph.facebook.com/v20.0/{video_id}/comments"
        payload = {
            "access_token": page_access_token,
            "message": comment_message
        }
        response = requests.post(url, data=payload)
        response_data = response.json()
        return response_data
    except Exception as e:
        print(f"Error commenting on video: {e}")
        return None

def upload_video_to_facebook(video_file_path, page_id, page_access_token, video_title, video_description):
    try:
        # Initiate the upload
        init_url = f"https://graph-video.facebook.com/v20.0/{page_id}/videos"
        init_params = {
            "upload_phase": "start",
            "access_token": page_access_token,
            "file_size": os.path.getsize(video_file_path)
        }
        init_response = requests.post(init_url, data=init_params).json()
        if 'upload_session_id' not in init_response:
            raise ValueError(f"Failed to initiate upload: {init_response}")
        
        upload_session_id = init_response['upload_session_id']
        video_id = init_response['video_id']

        # Upload the video file
        with open(video_file_path, 'rb') as video_file:
            while True:
                video_data = video_file.read(1024 * 1024 * 4)  # Read 4MB chunks
                if not video_data:
                    break
                upload_params = {
                    "upload_phase": "transfer",
                    "access_token": page_access_token,
                    "upload_session_id": upload_session_id,
                    "start_offset": init_response['start_offset'],
                    "video_file_chunk": video_data
                }
                upload_response = requests.post(init_url, files={"video_file_chunk": video_data}, data=upload_params).json()
                init_response['start_offset'] = upload_response['start_offset']

        # Finish the upload
        finish_url = f"https://graph-video.facebook.com/v20.0/{page_id}/videos"
        finish_params = {
            "upload_phase": "finish",
            "access_token": page_access_token,
            "upload_session_id": upload_session_id,
            "title": video_title,
            "description": video_description
        }
        finish_response = requests.post(finish_url, data=finish_params).json()

        return finish_response
    except Exception as e:
        print(f"Error uploading video: {e}")
        return {"error": str(e)}

def initialize_upload_session(page_id, page_access_token):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "upload_phase": "start",
            "access_token": page_access_token
        }
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()
        return response_data
    except Exception as e:
        print(f"Error initializing upload session: {e}")
        return None

def upload_video(video_file_path, upload_url, page_access_token):
    try:
        file_size = os.path.getsize(video_file_path)
        headers = {
            "Authorization": f"OAuth {page_access_token}",
            "offset": "0",
            "file_size": str(file_size)
        }
        with open(video_file_path, 'rb') as video_file:
            response = requests.post(upload_url, headers=headers, data=video_file)
        response_data = response.json()
        return response_data
    except Exception as e:
        print(f"Error uploading video: {e}")
        return None

def publish_reel(page_id, page_access_token, video_id, description):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
        payload = {
            "access_token": page_access_token,
            "video_id": video_id,
            "upload_phase": "finish",
            "video_state": "PUBLISHED",
            "description": description
        }
        response = requests.post(url, data=payload)
        response_data = response.json()
        return response_data
    except Exception as e:
        print(f"Error publishing reel: {e}")
        return None

video_title = text_quote
video_description = "https://tinyurl.com/1zx00SheinGiftCardNow " +  text_quote
video_file_path = f"{output_dir}/{FINAL_VIDEO}"

session_data = initialize_upload_session(PAGE_ID, PAGE_ACCESS_TOKEN)
print("Session Data:", session_data)
if "upload_url" in session_data:
    upload_url = session_data["upload_url"]
    upload_response = upload_video(video_file_path, upload_url, PAGE_ACCESS_TOKEN)
    print("Upload Response:", upload_response)
    if upload_response:
        video_id = session_data["video_id"]
        publish_response = publish_reel(PAGE_ID, PAGE_ACCESS_TOKEN, video_id, video_description)
        print("Publish Response:", publish_response)
        if 'success' in publish_response:
            comment_message = "https://tinyurl.com/1zx00SheinGiftCardNow" +"\n https://paxorex.blogspot.com/ Check out this awesome video!"
            comment_response = comment_on_video(video_id, PAGE_ACCESS_TOKEN, comment_message)
            print("Comment Response:", comment_response)

            if 'id' in comment_response:
                like_response = like_video(video_id, PAGE_ACCESS_TOKEN)
                print("Like Response:", like_response)
        else:
            print("Failed to publish video. Comment and like not posted.")
else:
    print("Failed to initialize upload session.")

def upload_video_to_instagram(video_file_path, caption, access_token, ig_user_id):
    try:
        # Step 1: Upload the video
        upload_url = f"https://graph.facebook.com/v15.0/{ig_user_id}/media"
        video_params = {
            'access_token': access_token,
            'media_type': 'VIDEO',
            'video_url': video_file_path,
            'caption': caption
        }

        upload_response = requests.post(upload_url, data=video_params).json()
        if 'id' not in upload_response:
            raise ValueError(f"Error uploading video: {upload_response}")

        creation_id = upload_response['id']

        # Step 2: Publish the video
        publish_url = f"https://graph.facebook.com/v15.0/{ig_user_id}/media_publish"
        publish_params = {
            'access_token': access_token,
            'creation_id': creation_id
        }

        publish_response = requests.post(publish_url, data=publish_params).json()
        return publish_response
    except Exception as e:
        print(f"Error uploading video to Instagram: {e}")
        return {"error": str(e)}

# Example usage for Instagram
ig_caption = text_quote
ig_response = upload_video_to_instagram(video_file_path, ig_caption, IG_ACCESS_TOKEN, IG_USER_ID)

if 'id' in ig_response:
    print('Video uploaded and published to Instagram successfully!')
    print('Response:', ig_response)
else:
    print('Failed to upload and publish video to Instagram.')
    print('Response:', ig_response)

def get_authenticated_service():
    try:
        credentials = Credentials(
            None,
            refresh_token=REFRESH_TOKEN,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET
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

slug = shorten(text_quote, width=90, placeholder="").replace('"', '').replace("Here's the polished and professional version of the blog post", '') \
    .replace('The title of the blog post is', '').replace(':', '').replace('<br>', '').replace('*', '') \
    .replace('The title of this edited blog post is', '').replace('Based on your edited blog post, I would title it', '') \
    .replace('Here is the edited blog post', '').replace('Here is the revised blog post', '') \
    .replace('The title is', '').replace('The title of this blog post is', '') \
    .replace('Here is a polished and professional version of the blog post', '')

# Remove unwanted special characters and non-alphanumeric characters
slg = re.sub(r'[^a-zA-Z0-9\s-]', '', slug.replace('The title is:', ''))
# Optionally, convert to lowercase and replace spaces with hyphens for the final slug format
slug_final = slg.lower().replace(" ", "-")

youtube_title = shorten(text_quote, width=90, placeholder="...")
youtube_description = "👉 Explore now at https://tinyurl.com/fileszc \nhttps://multiculturaltoolbox.com/blog/" + slug_final + " " +  text_quote
youtube_tags = ['cats', 'facts', 'https://edwardize.blogspot.com/', "http://multiculturaltoolbox.com/", "#cats", "#facts"]
youtube_category_id = '22'  # YouTube category ID
youtube_privacy_status = 'public'

response = upload_video_to_youtube(video_file_path, youtube_title, youtube_description, youtube_tags, youtube_category_id, youtube_privacy_status)

if response["id"]:
    with open(".env", "a") as env_file:
        env_file.write(f"\nYOUTUBE_VIDEO_ID={response['id']}\n")
    print("✅ YouTube metadata saved for GitHub Actions.")

    # Output metadata for GitHub Actions
    print(f"::set-output name=YOUTUBE_TITLE::{youtube_title}")
    print(f"::set-output name=YOUTUBE_DESCRIPTION::{youtube_description}")
    print(f"::set-output name=YOUTUBE_TAGS::{','.join(youtube_tags)}")
    print(f"::set-output name=YOUTUBE_CATEGORY_ID::{youtube_category_id}")
    print(f"::set-output name=YOUTUBE_PRIVACY_STATUS::{youtube_privacy_status}")
    print(f"::set-output name=YOUTUBE_VIDEO_ID::{response['id']}")

else:
    print("❌ Failed to upload video. No metadata saved.")


if 'id' in response:
    print('Video uploaded to YouTube successfully!')
    print('Response:', response)
    embed = f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{response["id"]}?si=29DB6WpyN3vo8Ez1" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>'

    keywords = "SEO, website, marketing, search engines"
    thumbnail = "default-thumbnail.jpg" 
    insert_blog_post_to_db(youtube_title, shorten(text_quote, width=90, placeholder="..."), embed + "" + text_quote, keywords, slug,  response.get("snippet", {}).get("thumbnails", {}).get("default", {}).get("url", "No Thumbnail Found"))
else:
    print('Failed to upload video to YouTube.')
    print('Response:', response)

