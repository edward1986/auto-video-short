import os
import re
import json
import sys
import base64
import requests
import smtplib
import mysql.connector

from os import environ
from datetime import datetime
from dotenv import load_dotenv
from textwrap import fill, shorten
from typing import Any, Optional, Tuple, Dict

from pyfiglet import Figlet
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    ColorClip,
)
from videoProcess.SoundCreate import make_audio
from videoProcess.VideoDownload import download_video
from videoProcess.Styling import (
    create_noise_overlay,
    create_gradient_glow,
    create_vignette,
    build_modern_captions,
    create_hook_clip,
    create_end_card,
    apply_zoom,
    get_text_clip,
    darken_clip,
)

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest

from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen


load_dotenv(".env")

WORD_URL = "https://www.merriam-webster.com/word-of-the-day"
CATFACT_URL = "https://catfact.ninja/fact"

# Pre-compiled regex patterns for performance
SANITIZE_TEXT_RE = re.compile(r"[^a-zA-Z0-9 \.\,\!\?\-]")
SANITIZE_INPUT_RE = re.compile(r"[^a-zA-Z0-9 ]")
WORD_OF_DAY_RE = re.compile(
    r'<h2\s+class="word-header-txt"\s*>\s*([^<]+)\s*</h2>', re.IGNORECASE
)


# =========================
# HTTP HELPERS
# =========================
def http_get_text(
    url: str, headers: Optional[dict] = None, timeout: int = 30
) -> Tuple[int, str]:
    req = UrlRequest(url, headers=headers or {}, method="GET")
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


def http_post_json(
    url: str, payload: dict, headers: Optional[dict] = None, timeout: int = 30
) -> Tuple[int, str, Dict[str, str]]:
    data = json.dumps(payload).encode("utf-8")

    base_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    if headers:
        base_headers.update(headers)

    req = UrlRequest(url, data=data, headers=base_headers, method="POST")

    try:
        with urlopen(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200))
            text = resp.read().decode("utf-8", errors="replace")
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return status, text, resp_headers
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        hdrs = (
            {k.lower(): v for k, v in getattr(e, "headers", {}).items()}
            if getattr(e, "headers", None)
            else {}
        )
        return int(e.code), body, hdrs
    except URLError as e:
        return 0, str(e), {}


# =========================
# CLOUDFLARE WHISPER
# =========================
def transcribe_audio_with_cloudflare(audio_file_path: str) -> dict:
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    model = os.getenv("CF_WHISPER_MODEL", "@cf/openai/whisper-tiny-en").strip()

    if not account_id:
        raise ValueError("Missing CLOUDFLARE_ACCOUNT_ID")
    if not api_token:
        raise ValueError("Missing CLOUDFLARE_API_TOKEN")
    if not os.path.exists(audio_file_path):
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/octet-stream",
    }

    with open(audio_file_path, "rb") as f:
        response = requests.post(url, headers=headers, data=f, timeout=120)

    response.raise_for_status()
    result = response.json()

    if not result.get("success", True):
        raise ValueError(f"Cloudflare Whisper failed: {result}")

    return result.get("result", result)


def build_phrase_level_text_clips(words, video_size, group_size=4):
    clips = []
    grouped = []
    current = []

    for item in words:
        word = str(item.get("word", "")).strip()
        if not word:
            continue

        current.append(item)

        if len(current) >= group_size:
            grouped.append(current)
            current = []

    if current:
        grouped.append(current)

    for group in grouped:
        text = " ".join(str(x.get("word", "")).strip() for x in group).strip()
        start = float(group[0].get("start", 0))
        end = float(group[-1].get("end", start + 1.0))

        if not text:
            continue
        if end <= start:
            end = start + 0.8

        txt = (
            get_text_clip(
                text,
                color="white",
                fontsize=55,
                align="center",
                method="caption",
                size=(900, None),
            )
            .set_start(start)
            .set_duration(end - start)
            .set_position(("center", "center"))
        )

        txt_w, txt_h = txt.size

        bg = (
            ColorClip(size=(txt_w + 40, txt_h + 20), color=(0, 0, 0))
            .set_opacity(0.5)
            .set_start(start)
            .set_duration(end - start)
            .set_position(("center", "center"))
        )

        clips.extend([bg, txt])

    return clips


# =========================
# GENERIC HELPERS
# =========================
def sanitize_text(s: str) -> str:
    return SANITIZE_TEXT_RE.sub("", s)


def sanitize_input(user_input: str) -> str:
    return SANITIZE_INPUT_RE.sub("", user_input)


def extract_word_of_the_day(html: str) -> Optional[str]:
    m = WORD_OF_DAY_RE.search(html)
    if not m:
        return None
    return m.group(1).strip()


def find_first_response_string(obj: Any) -> Optional[str]:
    if isinstance(obj, dict):
        if (
            "response" in obj
            and isinstance(obj["response"], str)
            and obj["response"].strip()
        ):
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
        print(f"{key}={value}")
        return

    with open(github_env, "a", encoding="utf-8") as f:
        f.write(f"{key}={value}\n")


def shorten_text(text, max_length=30):
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def split_text_chunks(text, max_length=90):
    words = text.split()
    chunks = []
    current_chunk = ""

    for word in words:
        if len(current_chunk) + len(word) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = word
        else:
            current_chunk += (" " + word) if current_chunk else word

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def video_to_base64(video_path):
    try:
        with open(video_path, "rb") as video_file:
            return base64.b64encode(video_file.read()).decode("utf-8")
    except Exception as e:
        print(f"Error converting video to base64: {e}")
        return None


# =========================
# ENV / CONFIG
# =========================
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

PUBLIC_VIDEO_URL = environ.get("PUBLIC_VIDEO_URL", "").strip()

cf_worker_url = os.getenv(
    "CF_WORKER_URL", "https://morning-dew-a596.ntcedge2.workers.dev"
).strip()
app_api_key = os.getenv("APP_API_KEY", "").strip()
model = os.getenv("MODEL", "@cf/meta/llama-4-scout-17b-16e-instruct").strip()

try:
    max_output_tokens = int(os.getenv("MAX_OUTPUT_TOKENS", "256"))
except ValueError:
    max_output_tokens = 256

sanitized_blog = ""
result_obj = {}

timestamp = datetime.now().strftime("%Y%m%d")
timestampFile = datetime.now().strftime("%H%M%S")
output_dir = f"output_{timestamp}"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

fig_font = Figlet(font="slant", justify="left")
print(fig_font.renderText("Auto Video Short!!!"))


# =========================
# FETCH WORD OF THE DAY
# =========================
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


# =========================
# FETCH CAT FACT
# =========================
status, cat_json = http_get_text(CATFACT_URL, headers={"User-Agent": "Mozilla/5.0"})
if status != 200:
    print(f"Failed to fetch cat fact, HTTP status: {status}", file=sys.stderr)

cat_fact = ""
try:
    cat_fact = json.loads(cat_json).get("fact", "")
except Exception:
    print("Failed to parse cat fact JSON.", file=sys.stderr)

sanitized_fact = sanitize_text(str(cat_fact))
prompt = f"{sanitized_fact} make a blog and use the word {word}"
print(prompt)


# =========================
# GENERATE BLOG USING WORKER
# =========================
if not cf_worker_url:
    print("Missing env var CF_WORKER_URL", file=sys.stderr)
    sys.exit(1)

payload = {
    "input": prompt,
    "instructions": "Write a short blog. Use simple English. Keep it clear and natural.",
    "model": model,
    "max_output_tokens": max_output_tokens,
}

headers = {}
if app_api_key:
    headers["X-APP-KEY"] = app_api_key

status, result_text, resp_headers = http_post_json(
    cf_worker_url, payload, headers=headers
)
content_type = (resp_headers.get("content-type") or "").lower()

if status == 0 or status >= 400:
    print(f"Worker HTTP error: {status}", file=sys.stderr)
    print(result_text[:800], file=sys.stderr)
    sys.exit(1)

if "application/json" not in content_type:
    if "error code: 1010" in result_text.lower():
        print("Blocked by Cloudflare (1010).", file=sys.stderr)
    else:
        print("Non-JSON response from Worker.", file=sys.stderr)

    print("Content-Type:", content_type, file=sys.stderr)
    print(result_text[:800], file=sys.stderr)
    sys.exit(1)

result_obj = json.loads(result_text)

blog = None
try:
    blog = (
        result_obj.get("result", {})
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content")
    )
except Exception:
    blog = None

if not blog:
    blog = (
        (
            (result_obj.get("result") or {}).get("response")
            if isinstance(result_obj.get("result"), dict)
            else None
        )
        or result_obj.get("response")
        or find_first_response_string(result_obj)
    )

if not blog or str(blog).strip().lower() == "null":
    print("Cloudflare Worker raw response:", file=sys.stderr)
    print(result_text, file=sys.stderr)
    sys.exit(1)

sanitized_blog = sanitize_text(str(blog)).replace("\n", " ").replace("\r", " ").strip()
print(sanitized_blog)


# =========================
# CREATE AUDIO + WHISPER TRANSCRIPTION
# =========================
text_quote = ""
transcribed_text = ""
whisper_words = []
whisper_vtt = ""

try:
    text_quote = sanitize_input(sanitized_blog)
    make_audio(text_quote, output_dir, timestampFile)

    audio_path = f"{output_dir}/{timestampFile}.mp3"

    try:
        whisper_result = transcribe_audio_with_cloudflare(audio_path)
        print("Whisper result:", json.dumps(whisper_result, indent=2))

        transcribed_text = whisper_result.get("text", "")
        whisper_words = whisper_result.get("words", [])
        whisper_vtt = whisper_result.get("vtt", "")

        with open(
            os.path.join(output_dir, "transcript.txt"), "w", encoding="utf-8"
        ) as f:
            f.write(transcribed_text)

        if whisper_vtt:
            with open(
                os.path.join(output_dir, "subtitles.vtt"), "w", encoding="utf-8"
            ) as f:
                f.write(whisper_vtt)

    except Exception as e:
        print(f"Error transcribing audio with Cloudflare Whisper: {e}")
        transcribed_text = text_quote
        whisper_words = []
        whisper_vtt = ""

except Exception as e:
    print(f"Error fetching quote or creating audio: {e}")
    sys.exit(1)


# =========================
# SAVE QUOTE TXT
# =========================
quote_file_path = os.path.join(output_dir, "quote.txt")
print(quote_file_path)

try:
    with open(quote_file_path, "w", encoding="utf-8") as file:
        file.write(shorten(text_quote, width=90, placeholder="..."))
    print(f"Quote saved to {quote_file_path}")
except Exception as e:
    print(f"Error saving quote to file: {e}")
    sys.exit(1)


# =========================
# DOWNLOAD VIDEO
# =========================
try:
    download_video(output_dir)
except Exception as e:
    print(f"Error downloading video: {e}")
    sys.exit(1)

video_path = f"{output_dir}/{VIDEO_NAME}"

if not os.path.exists(audio_path):
    print(f"Error: Audio file {audio_path} does not exist.")
    sys.exit(1)

if not os.path.exists(video_path):
    print(f"Error: Video file {video_path} does not exist.")
    sys.exit(1)


# =========================
# PREP VIDEO
# =========================
text_quote = fill(text_quote, width=30, fix_sentence_endings=True)
resolution = (1080, 1920)

try:
    audio_clip = AudioFileClip(audio_path)
except Exception as e:
    print(f"Error loading audio clip: {e}")
    sys.exit(1)

base64_video = ""
final_video_path = ""
MAX_DURATION = 59

try:
    total_duration = min(audio_clip.duration, MAX_DURATION)

    # target_resolution offloads resizing to FFmpeg during decoding, saving CPU/RAM.
    # We apply resize before loop to minimize transformation overhead on looped frames.
    video_clip = (
        VideoFileClip(video_path, audio=False, target_resolution=(1920, None))
        .resize(resolution)
        .loop(duration=total_duration)
        .set_audio(audio_clip.subclip(0, total_duration))
    )

    # 2026 Style: Darken for contrast and Ken Burns zoom
    video_clip = darken_clip(video_clip, factor=0.45)
    video_clip = apply_zoom(video_clip, total_duration)

    # 2-second hook title card
    hook_clip = create_hook_clip(word.upper())

    # Grain, Gradient Glow, and Vignette Overlays
    noise_overlay = create_noise_overlay(resolution, total_duration, opacity=0.1)
    glow_overlay = create_gradient_glow(
        resolution, total_duration, color=(200, 200, 255), opacity=0.15
    )
    vignette_overlay = create_vignette(resolution, total_duration, opacity=0.5)

    if whisper_words:
        text_clips = build_modern_captions(
            whisper_words,
            video_clip.size,
            highlight_word=word,
            phrase_mode=True,
        )
    else:
        # Fallback to modern captions even if whisper fails (simulated word timestamps)
        simulated_words = []
        words_list = text_quote.split()
        time_per_word = total_duration / max(len(words_list), 1)
        for i, w in enumerate(words_list):
            simulated_words.append(
                {"word": w, "start": i * time_per_word, "end": (i + 1) * time_per_word}
            )
        text_clips = build_modern_captions(
            simulated_words,
            video_clip.size,
            highlight_word=word,
            phrase_mode=True,
        )

    # 2026 style: Position captions in mobile safe area (y=0.55)
    text_clips = [c.set_position(("center", 0.55), relative=True) for c in text_clips]

    final = CompositeVideoClip(
        [
            video_clip,
            glow_overlay,
            noise_overlay,
            vignette_overlay,
            hook_clip,
        ]
        + text_clips,
        size=video_clip.size,
    )

    # Branded end card (2.5 seconds)
    end_card = create_end_card(resolution)

    from moviepy.editor import concatenate_videoclips

    # Clean transition between main content and end card (0.3s crossfade)
    final = concatenate_videoclips([final, end_card], method="compose", padding=-0.3)

    final_video_path = f"{output_dir}/{FINAL_VIDEO}"
    # Use multi-threaded video encoding for faster processing with a safe fallback
    threads = os.cpu_count() or 4
    final.write_videofile(
        final_video_path, codec="libx264", threads=threads, preset="fast"
    )

    # ✅ Explicitly close clips to release system resources
    final.close()
    video_clip.close()
    audio_clip.close()

except Exception as e:
    print(f"Error processing video: {e}")
    sys.exit(1)


# =========================
# EMAIL
# =========================
def send_email(subject, body, to, base64_video):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = to
        msg["Subject"] = subject

        html = f"""
        <div class="video-container">
            <video controls>
                <source src="data:video/mp4;base64,{base64_video}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        </div>
        <p>Quote: {text_quote}</p>
        <p>{body}</p>
        """

        msg.attach(MIMEText(html, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, to, msg.as_string())
        server.quit()

        print(f"Email sent to {to} with embedded video")
    except Exception as e:
        print(f"Error sending email: {e}")


print(text_quote)
if EMAIL_TO:
    # Only perform expensive base64 encoding if we're actually sending an email
    base64_video = video_to_base64(final_video_path)
    send_email(
        subject=text_quote,
        body="Please find the embedded video below.",
        to=EMAIL_TO,
        base64_video=base64_video,
    )


# =========================
# FACEBOOK
# =========================
def like_video(video_id, page_access_token):
    try:
        url = f"https://graph.facebook.com/v20.0/{video_id}/likes"
        payload = {"access_token": page_access_token}
        response = requests.post(url, data=payload)
        return response.json()
    except Exception as e:
        print(f"Error liking video: {e}")
        return None


def comment_on_video(video_id, page_access_token, comment_message):
    try:
        url = f"https://graph.facebook.com/v20.0/{video_id}/comments"
        payload = {"access_token": page_access_token, "message": comment_message}
        response = requests.post(url, data=payload)
        return response.json()
    except Exception as e:
        print(f"Error commenting on video: {e}")
        return None


def initialize_upload_session(page_id, page_access_token):
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
        headers = {"Content-Type": "application/json"}
        payload = {"upload_phase": "start", "access_token": page_access_token}
        response = requests.post(url, headers=headers, json=payload)
        return response.json()
    except Exception as e:
        print(f"Error initializing upload session: {e}")
        return None


def upload_video(video_file_path, upload_url, page_access_token):
    try:
        file_size = os.path.getsize(video_file_path)
        headers = {
            "Authorization": f"OAuth {page_access_token}",
            "offset": "0",
            "file_size": str(file_size),
        }

        with open(video_file_path, "rb") as video_file:
            response = requests.post(upload_url, headers=headers, data=video_file)

        try:
            return response.json()
        except Exception:
            return {"raw_response": response.text}
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
            "description": description,
        }
        response = requests.post(url, data=payload)
        return response.json()
    except Exception as e:
        print(f"Error publishing reel: {e}")
        return None


video_title = text_quote
video_description = text_quote
video_file_path = f"{output_dir}/{FINAL_VIDEO}"

session_data = initialize_upload_session(PAGE_ID, PAGE_ACCESS_TOKEN)
print("Session Data:", session_data)

if session_data and "upload_url" in session_data:
    upload_url = session_data["upload_url"]
    upload_response = upload_video(video_file_path, upload_url, PAGE_ACCESS_TOKEN)
    print("Upload Response:", upload_response)

    if upload_response is not None:
        video_id = session_data.get("video_id")
        publish_response = publish_reel(
            PAGE_ID, PAGE_ACCESS_TOKEN, video_id, video_description
        )
        print("Publish Response:", publish_response)

        if publish_response and publish_response.get("success"):
            comment_message = (
                "https://tinyurl.com/1zx00SheinGiftCardNow\n"
                "https://paxorex.blogspot.com/ Check out this awesome video!"
            )
            comment_response = comment_on_video(
                video_id, PAGE_ACCESS_TOKEN, comment_message
            )
            print("Comment Response:", comment_response)

            if comment_response and comment_response.get("id"):
                like_response = like_video(video_id, PAGE_ACCESS_TOKEN)
                print("Like Response:", like_response)
        else:
            print("Failed to publish video. Comment and like not posted.")
else:
    print("Failed to initialize upload session.")


# =========================
# INSTAGRAM
# =========================
def upload_video_to_instagram(video_url, caption, access_token, ig_user_id):
    try:
        if not video_url:
            raise ValueError("Instagram upload needs a PUBLIC_VIDEO_URL")

        upload_url = f"https://graph.facebook.com/v15.0/{ig_user_id}/media"
        video_params = {
            "access_token": access_token,
            "media_type": "VIDEO",
            "video_url": video_url,
            "caption": caption,
        }

        upload_response = requests.post(upload_url, data=video_params).json()
        if "id" not in upload_response:
            raise ValueError(f"Error uploading video: {upload_response}")

        creation_id = upload_response["id"]

        publish_url = f"https://graph.facebook.com/v15.0/{ig_user_id}/media_publish"
        publish_params = {"access_token": access_token, "creation_id": creation_id}

        publish_response = requests.post(publish_url, data=publish_params).json()
        return publish_response
    except Exception as e:
        print(f"Error uploading video to Instagram: {e}")
        return {"error": str(e)}


if PUBLIC_VIDEO_URL:
    ig_caption = text_quote
    ig_response = upload_video_to_instagram(
        PUBLIC_VIDEO_URL, ig_caption, IG_ACCESS_TOKEN, IG_USER_ID
    )

    if ig_response.get("id"):
        print("Video uploaded and published to Instagram successfully!")
        print("Response:", ig_response)
    else:
        print("Failed to upload and publish video to Instagram.")
        print("Response:", ig_response)
else:
    print("Skipping Instagram upload. PUBLIC_VIDEO_URL is missing.")


# =========================
# YOUTUBE
# =========================
def get_authenticated_service():
    try:
        credentials = Credentials(
            None,
            refresh_token=REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )
        credentials.refresh(GoogleAuthRequest())
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

        try:
            base, ext = os.path.splitext(video_file_path)
            new_file_path = f"{timestampFile}_{os.path.basename(base)}_retry{ext}"

            counter = 1
            while os.path.exists(new_file_path):
                new_file_path = (
                    f"{timestampFile}_{os.path.basename(base)}_retry{counter}{ext}"
                )
                counter += 1

            os.rename(video_file_path, new_file_path)
            print(f"Renamed file to: {new_file_path}")
        except Exception as rename_err:
            print(f"Failed to rename file after upload failure: {rename_err}")

        return {"error": str(e)}


# =========================
# MYSQL BLOG INSERT
# =========================
def insert_blog_post_to_db(title, summary, content, keywords, slug, thumbnail):
    try:
        mysql_host = environ.get("MYSQL_HOST")
        mysql_user = os.getenv("MYSQL_USER")
        mysql_password = os.getenv("MYSQL_PASSWORD")
        mysql_database = os.getenv("MYSQL_DATABASE")

        db = mysql.connector.connect(
            host=mysql_host,
            user=mysql_user,
            password=mysql_password,
            database=mysql_database,
        )

        cursor = db.cursor()
        created_at = updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

        pgSlug = (
            re.sub(
                r"[^a-zA-Z0-9\s-]",
                "",
                slug.replace("The title is", "").replace(
                    "The title of this blog post is", ""
                ),
            )
            .lower()
            .strip()
            .replace("\n", " ")
            .replace(" ", "-")
        )

        page_values = (
            pgSlug,
            "_self",
            "post",
            thumbnail,
            None,
            None,
            None,
            1,
            1,
            1,
            1,
            1,
            1,
            None,
            created_at,
            updated_at,
        )

        cursor.execute(page_sql, page_values)
        db.commit()

        page_id = cursor.lastrowid
        print(f"Inserted page ID: {page_id}")

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

        clean_title = (
            title.replace("The title is", "")
            .replace("I think your revised blog post looks great", "")
            .replace(
                "Here is a rewritten version of the blog post with a polished and professional tone, grammar, and readability",
                "",
            )
            .replace("The title you provided is", "")
            .replace(
                "Here is the polished and professional version of the blog post", ""
            )
            .replace("Here's the revised blog post", "")
            .replace("The title of this blog post is", "")
            .strip('"')
            .replace("\n", " ")
        )

        values = (
            "en",
            clean_title,
            1,
            1,
            1,
            clean_title,
            clean_title,
            clean_title,
            "<p>" + content.replace("\n", "<br>") + "</p>",
            page_id,
            created_at,
            updated_at,
        )

        cursor.execute(sql, values)
        db.commit()

        cursor.close()
        db.close()

    except Exception as e:
        print(f"Error inserting blog post to DB: {e}")


# =========================
# FINAL YOUTUBE METADATA / DB
# =========================
slug = (
    shorten(text_quote, width=90, placeholder="")
    .replace('"', "")
    .replace("Here's the polished and professional version of the blog post", "")
    .replace("The title of the blog post is", "")
    .replace(":", "")
    .replace("<br>", "")
    .replace("*", "")
    .replace("The title of this edited blog post is", "")
    .replace("Based on your edited blog post, I would title it", "")
    .replace("Here is the edited blog post", "")
    .replace("Here is the revised blog post", "")
    .replace("The title is", "")
    .replace("The title of this blog post is", "")
    .replace("Here is a polished and professional version of the blog post", "")
)

slg = re.sub(r"[^a-zA-Z0-9\s-]", "", slug.replace("The title is:", ""))
slug_final = slg.lower().replace(" ", "-")

youtube_title = shorten(text_quote, width=90, placeholder="...")
youtube_description = (
    "👉 Explore now at https://multiculturaltoolbox.com/blog/"
    + slug_final
    + " "
    + text_quote
)
youtube_tags = [
    "cats",
    "facts",
    "https://edwardize.blogspot.com/",
    "http://multiculturaltoolbox.com/",
    "#cats",
    "#facts",
]
youtube_category_id = "22"
youtube_privacy_status = "public"

response = upload_video_to_youtube(
    video_file_path,
    youtube_title,
    youtube_description,
    youtube_tags,
    youtube_category_id,
    youtube_privacy_status,
)

if response.get("id"):
    with open(".env", "a", encoding="utf-8") as env_file:
        env_file.write(f"\nYOUTUBE_VIDEO_ID={response['id']}\n")

    print("✅ YouTube metadata saved for GitHub Actions.")
    print(f"::set-output name=YOUTUBE_TITLE::{youtube_title}")
    print(f"::set-output name=YOUTUBE_DESCRIPTION::{youtube_description}")
    print(f"::set-output name=YOUTUBE_TAGS::{','.join(youtube_tags)}")
    print(f"::set-output name=YOUTUBE_CATEGORY_ID::{youtube_category_id}")
    print(f"::set-output name=YOUTUBE_PRIVACY_STATUS::{youtube_privacy_status}")
    print(f"::set-output name=YOUTUBE_VIDEO_ID::{response['id']}")
else:
    print("❌ Failed to upload video. No metadata saved.")

if response.get("id"):
    print("Video uploaded to YouTube successfully!")
    print("Response:", response)

    embed = (
        f'<iframe width="560" height="315" '
        f'src="https://www.youtube.com/embed/{response["id"]}?si=29DB6WpyN3vo8Ez1" '
        f'title="YouTube video player" frameborder="0" '
        f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
        f'referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>'
    )

    keywords = "SEO, website, marketing, search engines"
    thumbnail = (
        response.get("snippet", {})
        .get("thumbnails", {})
        .get("default", {})
        .get("url", "No Thumbnail Found")
    )

    insert_blog_post_to_db(
        youtube_title,
        shorten(text_quote, width=90, placeholder="..."),
        embed + text_quote,
        keywords,
        slug,
        thumbnail,
    )
else:
    print("Failed to upload video to YouTube.")
    print("Response:", response)
