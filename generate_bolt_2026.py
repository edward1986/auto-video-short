import os
import sys
import json
import random
from PIL import Image

# Technical Constraint: Ensure Python 3.10+
if sys.version_info < (3, 10):
    sys.exit("Error: This system requires Python 3.10 or higher to run.")

# Monkeypatch for MoviePy 1.0.3 compatibility with Pillow 10+
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

import moviepy.editor as editor
from moviepy.editor import CompositeVideoClip, concatenate_videoclips
from videoProcess.Styling import (
    create_noise_overlay,
    create_gradient_glow,
    create_hook_clip,
    create_end_card,
    apply_zoom,
    darken_clip,
    create_flash_transition,
    create_vignette,
    create_progress_bar,
    apply_dynamic_cuts,
    build_modern_captions,
    get_text_clip,
    apply_kinetic_pop,
    apply_shake,
)


def load_trivia():
    with open("questions.json", "r", encoding="utf-8") as file:
        data = json.load(file)

    # Combine all categories
    all_questions = []
    for category in ["science", "animals", "games"]:
        if category in data:
            all_questions.extend(data[category])

    return random.choice(all_questions)


def generate():
    resolution = (1080, 1920)
    bg_path = "parkour.mp4"
    audio_path = "music.mp3"
    font_path = "default.ttf"
    output_path = "bolt_2026_short.mp4"

    # Robustness: Check if assets exist
    for path in [bg_path, audio_path, font_path, "questions.json"]:
        if not os.path.exists(path):
            sys.exit(
                f"Error: Required asset '{path}' not found. Please ensure it exists in the root directory."
            )

    question_data = load_trivia()
    print(f"Selected Question: {question_data['title']}")

    # 1. Background and Audio Setup
    bg_clip = editor.VideoFileClip(
        bg_path, audio=False, target_resolution=(1920, None)
    ).resize(resolution)
    audio_clip = editor.AudioFileClip(audio_path)

    q_dur = 8.0
    a_dur = 4.0
    main_duration = q_dur + a_dur
    end_card_duration = 2.5
    total_duration = main_duration + end_card_duration

    if bg_clip.duration < main_duration:
        bg_clip = bg_clip.loop(duration=main_duration)
    else:
        bg_clip = bg_clip.subclip(0, main_duration)

    if audio_clip.duration < total_duration:
        audio_clip = audio_clip.loop(duration=total_duration)
    else:
        audio_clip = audio_clip.subclip(0, total_duration)

    # 2. Apply Background Effects
    # Split into Question and Answer segments for dynamic zoom reset
    bg_q = bg_clip.subclip(0, q_dur)
    bg_q = apply_zoom(bg_q, q_dur, start_scale=1.0, end_scale=1.1)

    bg_a = bg_clip.subclip(q_dur, q_dur + a_dur)
    bg_a = apply_zoom(bg_a, a_dur, start_scale=1.05, end_scale=1.2)

    bg_clip = concatenate_videoclips([bg_q, bg_a], method="chain")
    bg_clip = darken_clip(bg_clip, factor=0.4)
    bg_clip = apply_dynamic_cuts(bg_clip, segment_duration=2.5)

    # 3. Overlays (Glow, Noise, Vignette, Progress Bar)
    noise = create_noise_overlay(resolution, main_duration, opacity=0.1)
    glow = create_gradient_glow(
        resolution, main_duration, color=[(0, 255, 128), (255, 255, 255)], opacity=0.15
    )
    vignette = create_vignette(resolution, main_duration, opacity=0.4)
    progress_bar = create_progress_bar(resolution, main_duration, color=(0, 255, 128))
    flash = create_flash_transition(resolution).set_start(q_dur)

    # 4. Content - Hook, Question, Answers
    hook = create_hook_clip(
        "TRIVIA CHALLENGE", video_size=resolution, duration=2.0, font=font_path
    )

    # Question Captions
    raw_words = question_data["title"].split()
    time_per_word = (q_dur - 2.0) / max(len(raw_words), 1)
    words_data = []
    for i, w in enumerate(raw_words):
        words_data.append(
            {
                "word": w,
                "start": 2.0 + (i * time_per_word),
                "end": 2.0 + ((i + 1) * time_per_word),
            }
        )

    captions = build_modern_captions(
        words_data,
        resolution,
        highlight_word="NOT",  # Common trivia highlight
        font=font_path,
        phrase_mode=True,
        y_pos=0.2,
    )

    # Answer Choices
    answer_clips = []
    labels = ["A", "B", "C", "D"]
    for i, ans in enumerate(question_data["answers"]):
        target_y = 0.45 + (i * 0.08)
        ans_clip = (
            get_text_clip(
                f"{labels[i]}: {ans}".upper(),
                fontsize=80,
                color="white",
                font=font_path,
                stroke_color="black",
                stroke_width=4,
                size=(900, None),
                align="center",
            )
            .set_start(3.0 + (i * 0.2))
            .set_duration(q_dur - (3.0 + (i * 0.2)))
        )

        ans_clip = ans_clip.set_position(("center", target_y), relative=True)
        ans_clip = apply_kinetic_pop(ans_clip, duration=0.2, scale=1.1)
        answer_clips.append(ans_clip)

    # Correct Answer Reveal
    correct_text = f"CORRECT: {question_data['answers'][question_data['correct']]}"
    reveal = (
        get_text_clip(
            correct_text.upper(),
            fontsize=120,
            color="#00FF00",
            font=font_path,
            stroke_color="black",
            stroke_width=6,
            size=(1000, None),
            align="center",
        )
        .set_start(q_dur)
        .set_duration(a_dur)
        .set_position("center")
    )
    reveal = apply_kinetic_pop(reveal, duration=0.4, scale=1.5)
    reveal = apply_shake(reveal, duration=0.5)

    # 5. Composite Main Segment
    main_video = CompositeVideoClip(
        [bg_clip, glow, noise, vignette, hook, flash, progress_bar, reveal]
        + captions
        + answer_clips,
        size=resolution,
        use_bgclip=True,
    )

    # 6. End Card
    end_card = create_end_card(
        resolution,
        duration=end_card_duration,
        text="SUBSCRIBE FOR MORE",
        font=font_path,
    )

    # 7. Final Concatenation
    final_video = concatenate_videoclips(
        [main_video, end_card], method="compose", padding=-0.2
    )
    final_video = final_video.set_audio(audio_clip)

    # 8. Export
    if not os.path.exists("out"):
        os.makedirs("out")

    final_video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=os.cpu_count() or 4,
        preset="ultrafast",  # Faster for this environment
    )

    print(f"Video generated successfully: {output_path}")


if __name__ == "__main__":
    generate()
