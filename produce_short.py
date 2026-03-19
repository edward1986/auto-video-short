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

    print(f"Selected Question: {question['title']}")
    print(f"Answers: {question['answers']}")
    print(f"Correct Answer Index: {question['correct']}")

    # ✅ Load background and music once to avoid repeated file I/O
    bg_clip = editor.VideoFileClip(background)
    audio_clip = editor.AudioFileClip(music)

    background_duration = bg_clip.duration
    background = resize(
        (
            bg_clip.cutout(
                0, max(1, round(background_duration) - 65)
            )  # ✅ Ensure valid range
            .set_duration(full_question_duration)
            .set_position(("center", "center"))
        ),
        height=1920,
    )

    music_duration = audio_clip.duration
    available_music_time = max(1, music_duration - full_question_duration)
    music_start_time = max(
        1, min(available_music_time, randint(1, int(available_music_time)))
    )

    music = volumex(
        editor.CompositeAudioClip(
            [audio_clip.cutout(0, music_start_time).set_end(full_question_duration)]
        ),
        0.6,
    )

    clips = []

    # ✅ Display the selected question
    question_text = (
        editor.TextClip(
            question["title"],
            fontsize=90,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(1080, None),
            font=font,
        )
        .set_position(("center", 0.03), relative=True)
        .set_start(0)
        .set_duration(clip_durations["question"])
    )

    clips.append(question_text)

    # ✅ Display answer choices
    answer_labels = list("ABCD")
    answer_texts = [
        editor.TextClip(
            f"{answer_labels[i]} - {question['answers'][i]}",
            fontsize=90,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(1080, None),
            font=font,
        )
        .set_position(("center", 0.35 + (i / 7)), relative=True)
        .set_start(0)
        .set_duration(clip_durations["question"])
        for i in range(len(question["answers"]))
    ]
    clips += answer_texts

    # ✅ Countdown timer (10 to 0)
    countdown_texts = [
        editor.TextClip(
            str(clip_durations["question"] - i),
            fontsize=120,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(1080, None),
            font=font,
        )
        .set_start(i)
        .set_duration(1)
        .set_position(("center", 0.87), relative=True)
        for i in range(clip_durations["question"])
    ]
    clips += countdown_texts

    # ✅ Highlight the correct answer
    correct_answer_text = (
        editor.TextClip(
            question["answers"][question["correct"]],
            fontsize=120,
            color="#00ff00",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(1080, None),
            font=font,
        )
        .set_start(clip_durations["question"])
        .set_duration(clip_durations["answer"])
        .set_position("center")
    )

    clips.append(correct_answer_text)

    # ✅ Combine all clips
    result: editor.CompositeVideoClip = editor.CompositeVideoClip(
        [background, *clips], size=(1080, 1920)
    ).set_audio(music)

    # ✅ Export the final video
    threads = os.cpu_count() or 4
    result.write_videofile(
        output,
        fps=24,
        audio_codec="aac",
        threads=threads,
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
