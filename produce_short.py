from random import randint
import json
from moviepy.video.io.VideoFileClip import VideoFileClip  # ✅ Corrected
from moviepy.audio.io.AudioFileClip import AudioFileClip  # ✅ Corrected
from moviepy.video.VideoClip import TextClip  # ✅ Corrected
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip  # ✅ Fixed
from moviepy.audio.AudioClip import CompositeAudioClip  # ✅ Fixed
from moviepy.video.fx import *
clip_durations = {
    "question": 10,
    "answer": 2.5
}
full_question_duration = sum(clip_durations.values())


class Question:
    title: str
    answers: list[str]
    correct_answer: int

    def __init__(self):
        self.answers = []


def produce_short(
    questions: list[Question],
    background: str,
    music: str,
    font: str,
    output: str
):
    question_count = len(questions)

    background_duration = VideoFileClip(background).duration
    background = resize(
        (
            VideoFileClip(background)
            .cutout(0, randint(1, round(background_duration) - 65))
            .set_duration(full_question_duration * question_count)
            .set_position(("center", "center"))
        ),
        height=1920
    )

    music_duration = AudioFileClip(music).duration
    music = volumex(
        CompositeAudioClip([
            AudioFileClip(music)
            .cutout(0, randint(
                1, 
                int(music_duration - full_question_duration * question_count)
            ))
            .set_end(full_question_duration * question_count)
        ]), 
        0.6
    )

    clips = []

    for question_index, question in enumerate(questions):
        question_text = (
            TextClip(
                question["title"],
                fontsize=90, 
                color="white", 
                stroke_color="black", 
                stroke_width=2,
                method="caption",
                size=(1080, None),
                font=font
            )
            .set_position(("center", 0.03), relative=True)
            .set_start(question_index * full_question_duration)
            .set_duration(clip_durations["question"])
        )
        clips.append(question_text)

        answer_texts = [
            (
                TextClip(
                    f"{list('ABCD')[i]} - {question['answers'][i]}", 
                    fontsize=90, 
                    color="white", 
                    stroke_color="black", 
                    stroke_width=2,
                    method="caption",
                    size=(1080, None),
                    font=font
                )
                .set_position(("center", 0.35 + (i / 7)), relative=True)
                .set_start(question_index * full_question_duration)
                .set_duration(clip_durations["question"])
            ) for i in range(len(question["answers"]))
        ]
        clips += answer_texts

        countdown_texts = [
            (
                TextClip(
                    str(clip_durations["question"] - i), 
                    fontsize=120, 
                    color="white", 
                    stroke_color="black", 
                    stroke_width=2,
                    method="caption",
                    size=(1080, None),
                    font=font
                )
                .set_start(question_index * full_question_duration + i)
                .set_duration(1)
                .set_position(("center", 0.87), relative=True)
            ) for i in range(clip_durations["question"])
        ]
        clips += countdown_texts

        correct_answer_text = (
            TextClip(
                question["answers"][question["correct"]], 
                fontsize=120, 
                color="#00ff00", 
                stroke_color="black", 
                stroke_width=2,
                method="caption",
                size=(1080, None),
                font=font
            )
            .set_start(question_index * full_question_duration + clip_durations["question"])
            .set_duration(clip_durations["answer"])
            .set_position("center")
        )
        clips.append(correct_answer_text)

    result: CompositeVideoClip = (
        CompositeVideoClip(
            [
                background,
                *clips
            ], 
            size=(1080, 1920)
        )
        .set_audio(music)
    )

    result.write_videofile(
        output, 
        fps=24, 
        audio_codec="aac",
        threads=4,
        temp_audiofile="out/TEMP_trivia.mp4"
    )


if __name__ == "__main__":
    
    # Read JSON from file instead of command-line argument
    with open("questions.json", "r", encoding="utf-8") as file:
        args = json.load(file)

        # Merge "animals" and "games" into one question list
        args["questions"] = args.get("animals", []) + args.get("games", [])
    
        produce_short(
            questions=args["questions"],
            background=args["assets"]["background"],
            music=args["assets"]["music"],
            font=args["assets"]["font"],
            output=args["output"]
        )
