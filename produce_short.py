from random import randint, choice
from datetime import datetime
import json
import random
import os
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import moviepy.editor as editor
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


def produce_short(
    questions: list[Question], background: str, music: str, font: str, output: str
):
    # ✅ Select one random question
    question = choice(questions)
    resolution = (1080, 1920)

    print(f"Selected Question: {question['title']}")
    print(f"Answers: {question['answers']}")
    print(f"Correct Answer Index: {question['correct']}")

    # ✅ Load background and music once to avoid repeated file I/O
    # target_resolution offloads resizing to FFmpeg during decoding for better performance.
    bg_clip = editor.VideoFileClip(background, target_resolution=(1920, None))
    audio_clip = editor.AudioFileClip(music)

    background_duration = bg_clip.duration
    background_clip = resize(
        (
            bg_clip.cutout(
                0, max(1, round(background_duration) - 65)
            )  # ✅ Ensure valid range
            .set_duration(full_question_duration)
            .set_position(("center", "center"))
        ),
        height=1920,
    )
    # Apply slow zoom for 2026 style
    background_clip = apply_zoom(background_clip, full_question_duration)

    music_duration = audio_clip.duration
    available_music_time = max(1, music_duration - full_question_duration)
    music_start_time = max(
        1, min(available_music_time, randint(1, int(available_music_time)))
    )

    music_track = volumex(
        audio_clip.cutout(0, music_start_time).set_end(full_question_duration),
        0.6,
    )

    # Overlays
    noise_overlay = create_noise_overlay(resolution, full_question_duration)
    glow_overlay = create_gradient_glow(resolution, full_question_duration)

    # 2-second high-impact hook
    hook_clip = create_hook_clip("TRIVIA TIME!", font=font)

    clips = [background_clip, glow_overlay, noise_overlay, hook_clip]

    # ✅ Display the selected question - Bold and kinetic
    question_text = (
        editor.TextClip(
            question["title"],
            fontsize=90,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(1000, None),  # Safe margins
            font=font,
        )
        .set_position(("center", 0.05), relative=True)
        .set_start(0)
        .set_duration(clip_durations["question"])
    )
    question_text = apply_kinetic_pop(question_text)

    clips.append(question_text)

    # ✅ Display answer choices with labels
    answer_labels = list("ABCD")
    for i in range(len(question["answers"])):
        answer_clip = (
            editor.TextClip(
                f"{answer_labels[i]} - {question['answers'][i]}",
                fontsize=85,
                color="white",
                stroke_color="black",
                stroke_width=2,
                method="caption",
                size=(1000, None),
                font=font,
            )
            .set_position(("center", 0.35 + (i / 8)), relative=True)
            .set_start(0)
            .set_duration(clip_durations["question"])
        )
        # Staggered pop animations for answers
        answer_clip = apply_kinetic_pop(answer_clip, duration=0.1 + (i * 0.05))
        clips.append(answer_clip)

    # ✅ Countdown timer (10 to 0)
    for i in range(clip_durations["question"]):
        countdown_clip = (
            editor.TextClip(
                str(clip_durations["question"] - i),
                fontsize=130,
                color="white",
                stroke_color="black",
                stroke_width=3,
                method="label",
                font=font,
            )
            .set_start(i)
            .set_duration(1)
            .set_position(("center", 0.88), relative=True)
        )
        # Pulse every second
        countdown_clip = apply_kinetic_pop(countdown_clip, duration=0.2, scale=1.3)
        clips.append(countdown_clip)

    # ✅ Highlight the correct answer - Modern kinetic reveal
    correct_answer_reveal = (
        editor.TextClip(
            f"CORRECT:\n{question['answers'][question['correct']]}",
            fontsize=130,
            color="#00ff00",
            stroke_color="black",
            stroke_width=4,
            method="caption",
            size=(1000, None),
            font=font,
        )
        .set_start(clip_durations["question"])
        .set_duration(clip_durations["answer"])
        .set_position("center")
    )
    correct_answer_reveal = apply_kinetic_pop(
        correct_answer_reveal, duration=0.3, scale=1.4
    )
    clips.append(correct_answer_reveal)

    # ✅ Combine all clips
    result: editor.CompositeVideoClip = editor.CompositeVideoClip(
        clips, size=resolution
    ).set_audio(music_track)

    # Branded end card (2 seconds)
    end_card = create_end_card(resolution, font=font)
    from moviepy.editor import concatenate_videoclips

    final_video = concatenate_videoclips([result, end_card])

    # ✅ Export the final video - Use multi-threaded video encoding with a safe fallback
    final_video.write_videofile(
        output,
        fps=24,
        audio_codec="aac",
        threads=os.cpu_count() or 4,
        preset="fast",
        temp_audiofile="out/TEMP_trivia.mp4",
    )
    youtube_title = shorten(question["title"], width=90, placeholder="...")
    youtube_description = (
        "👉 Explore now at https://tinyurl.com/1zx00SheinGiftCardNow \nhttps://multiculturaltoolbox.com/blog/"
        + " "
        + question["title"]
    )
    youtube_tags = [
        "cats",
        "facts",
        "https://edwardize.blogspot.com/",
        "http://multiculturaltoolbox.com/",
        "#cats",
        "#facts",
    ]
    youtube_category_id = "22"  # YouTube category ID
    youtube_privacy_status = "public"

    response = upload_video_to_youtube(
        video_file_path,
        youtube_title,
        youtube_description,
        youtube_tags,
        youtube_category_id,
        youtube_privacy_status,
    )

    if "id" in response:
        print("Video uploaded to YouTube successfully!")
        print("Response:", response)
    else:
        print("Failed to upload video to YouTube.")
        print("Response:", response)

    # ✅ Explicitly close clips to release system resources
    bg_clip.close()
    audio_clip.close()


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

        # Ensure we don't overwrite an existing file
        counter = 1
        while os.path.exists(new_file_path):
            new_file_path = f"{timestampFile}_{base}_retry{counter}{ext}"
            counter += 1

        os.rename(video_file_path, new_file_path)
        print(f"Renamed file to: {new_file_path}")

        return {"error": str(e)}


if __name__ == "__main__":
    # Load questions from JSON file
    with open("questions.json", "r", encoding="utf-8") as file:
        args = json.load(file)

        # Merge "animals" and "games" categories if present
        args["questions"] = (
            args.get("science", []) + args.get("animals", []) + args.get("games", [])
        )
        with open("tracks.json", "r", encoding="utf-8") as file:
            tracks = json.load(file)

        # Select a random music track
        selected_track = random.choice(tracks)  # Picks a random dictionary

        # Extract filename and dropTime
        random_music_track = selected_track["filename"]
        drop_time = selected_track["dropTime"]

        produce_short(
            questions=args["questions"],
            background=args["assets"]["background"],
            music=random_music_track,
            font=args["assets"]["font"],
            output=args["output"],
        )
