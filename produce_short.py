from random import randint, choice
from datetime import datetime
import json
import random
import os
from PIL import Image

# Monkeypatch for MoviePy 1.0.3 compatibility with Pillow 10+
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import moviepy.editor as editor
from moviepy.editor import concatenate_videoclips
from moviepy.video.fx.resize import resize
from moviepy.audio.fx.volumex import volumex
from textwrap import shorten
from videoProcess.Styling import (
    create_noise_overlay,
    create_gradient_glow,
    create_hook_clip,
    create_end_card,
    apply_zoom,
    apply_kinetic_pop,
    apply_slide_in,
    apply_shake,
    build_modern_captions,
    get_text_clip,
    darken_clip,
    create_flash_transition,
    create_vignette,
    create_progress_bar,
    apply_dynamic_cuts,
)

CLIENT_ID = "553209643758-dn4375pj94hssfcipff2e1kn8eeqoprr.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REFRESH_TOKEN = "1//0eo_Nlm6px-u0CgYIARAAGA4SNwF-L9IrN2zK_M5f3PUFHIn52Vp5Mmb3FbWVXWMHEBa94fLxt3_Z2Ljy6INmzrkyXoX4kcRd95o"
video_file_path = "output.mp4"
clip_durations = {"question": 10, "answer": 2.5}
full_question_duration = sum(clip_durations.values())
timestamp = datetime.now().strftime("%Y%m%d")
timestampFile = datetime.now().strftime("%H%M%S")
output_dir = f"output_{timestamp}"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)


class Question:
    title: str
    answers: list[str]
    correct_answer: int

    def __init__(self):
        self.answers = []


def produce_short(questions: list[Question], background: str, music: str, font: str, output: str):
    """Render a clean 9:16 quiz short without overlapping text or distortion."""
    question = choice(questions)
    W, H = 1080, 1920
    q_dur = float(clip_durations["question"])
    a_dur = float(clip_durations["answer"])
    total = q_dur + a_dur

    # Avoid stretching the original video. Scale to cover 9:16, then center-crop.
    bg_source = editor.VideoFileClip(background, audio=False)
    music_source = editor.AudioFileClip(music)
    bg = bg_source.loop(duration=total) if bg_source.duration < total else bg_source.subclip(0, total)
    scale = max(W / bg.w, H / bg.h)
    bg = bg.resize(scale)
    bg = bg.crop(x_center=bg.w / 2, y_center=bg.h / 2, width=W, height=H)
    bg = darken_clip(bg, factor=0.34)

    def fit_text(value, font_size, top, max_height, *, color="white",
                 start=0, until=None, max_width=900, stroke=3):
        # Reserve a real pixel rectangle for each text element.
        clip = get_text_clip(
            str(value), fontsize=font_size, font=font, color=color,
            stroke_color="black", stroke_width=stroke,
            size=(max_width, None), align="center",
        )
        factor = min(1.0, max_width / max(clip.w, 1), max_height / max(clip.h, 1))
        if factor < 1:
            clip = clip.resize(factor)
        x = (W - clip.w) / 2
        y = top + (max_height - clip.h) / 2
        return clip.set_position((x, y)).set_start(start).set_duration(
            (total if until is None else until) - start
        )

    layers = [bg]
    # Distinct safe zones: title 190-330, question 350-650,
    # choices 700-1380, countdown 1480-1680.
    layers.append(fit_text("TRIVIA TIME!", 104, 190, 140,
                           color="#36FF79", until=q_dur))
    layers.append(fit_text(question["title"].upper(), 80, 350, 300,
                           until=q_dur))

    answers = question["answers"]
    if len(answers) > 4:
        raise ValueError("Video layout supports no more than four choices")
    for i, answer in enumerate(answers):
        start = 0.35 + i * 0.18
        layers.append(fit_text(
            f"{chr(65 + i)} - {str(answer).upper()}", 68,
            710 + i * 165, 140, start=start, until=q_dur,
        ))

    for elapsed in range(int(q_dur)):
        layers.append(fit_text(str(int(q_dur) - elapsed), 145,
                               1480, 210, start=float(elapsed),
                               until=float(elapsed + 1), max_width=400))

    # Reveal uses separate times and therefore cannot overlap the options.
    layers.append(fit_text("CORRECT ANSWER", 85, 550, 160,
                           color="#36FF79", start=q_dur, until=total))
    layers.append(fit_text(str(answers[question["correct"]]).upper(),
                           112, 780, 310, start=q_dur, until=total))
    layers.append(create_progress_bar((W, H), total, color=(54, 255, 121)))

    track = music_source.fx(editor.afx.audio_loop, duration=total) if music_source.duration < total else music_source.subclip(0, total)
    track = volumex(track, 0.55).set_duration(total)
    result = editor.CompositeVideoClip(layers, size=(W, H)).set_duration(total).set_audio(track)

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    result.write_videofile(
        output, codec="libx264", fps=24, audio_codec="aac",
        audio_bitrate="160k", threads=4, preset="medium",
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    youtube_title = shorten(question["title"], width=90, placeholder="...")
    youtube_tags = ["trivia", "quiz", "facts", "#shorts"]
    response = upload_video_to_youtube(
        output, youtube_title, question["title"], youtube_tags, "22", "public"
    )
    print("YouTube upload:", response)
    result.close()
    bg_source.close()
    music_source.close()


def get_authenticated_service():
    try:
        credentials = Credentials(
            None,
            refresh_token=REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
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
        base, ext = os.path.splitext(video_file_path)
        new_file_path = f"{timestampFile}_{base}_retry{ext}"

        counter = 1
        while os.path.exists(new_file_path):
            new_file_path = f"{timestampFile}_{base}_retry{counter}{ext}"
            counter += 1

        return {"error": str(e)}


if __name__ == "__main__":
    # Load questions from JSON file
    with open("questions.json", "r", encoding="utf-8") as file:
        args = json.load(file)

        args["questions"] = (
            args.get("science", []) + args.get("animals", []) + args.get("games", [])
        )
        with open("tracks.json", "r", encoding="utf-8") as file:
            tracks = json.load(file)

        selected_track = random.choice(tracks)
        random_music_track = selected_track["filename"]

        produce_short(
            questions=args["questions"],
            background=args["assets"]["background"],
            music=random_music_track,
            font=args["assets"]["font"],
            output=args["output"],
        )
