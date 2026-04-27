import os
import sys
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
)


def generate():
    resolution = (1080, 1920)
    bg_path = "parkour.mp4"
    audio_path = "music.mp3"
    font_path = "default.ttf"
    output_path = "premium_2026_short.mp4"

    # Robustness: Check if assets exist
    for path in [bg_path, audio_path, font_path]:
        if not os.path.exists(path):
            sys.exit(
                f"Error: Required asset '{path}' not found. Please ensure it exists in the root directory before running this generator."
            )

    # 1. Background and Audio Setup
    bg_clip = editor.VideoFileClip(
        bg_path, audio=False, target_resolution=(1920, None)
    ).resize(resolution)
    audio_clip = editor.AudioFileClip(audio_path)

    main_duration = 15.0
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
    # Ken Burns Zoom (1.0 to 1.15)
    bg_clip = apply_zoom(bg_clip, main_duration, start_scale=1.0, end_scale=1.15)
    # Darken for contrast
    bg_clip = darken_clip(bg_clip, factor=0.45)
    # Dynamic cuts every 2.5s
    bg_clip = apply_dynamic_cuts(bg_clip, segment_duration=2.5)

    # 3. Overlays
    noise = create_noise_overlay(resolution, main_duration, opacity=0.1)
    # Neon Green and Cyan Glow
    glow = create_gradient_glow(
        resolution, main_duration, color=[(0, 255, 128), (0, 255, 255)], opacity=0.15
    )
    vignette = create_vignette(resolution, main_duration, opacity=0.5)
    progress_bar = create_progress_bar(resolution, main_duration, color=(0, 255, 128))
    flash = create_flash_transition(resolution).set_start(2.0)

    # 4. Content - Hook (0-2s)
    hook = create_hook_clip(
        "MASTER 2026 STYLE", video_size=resolution, duration=2.0, font=font_path
    )

    # 5. Script for Captions
    # Core Message (3-10s): Large kinetic typography, bold, minimal.
    # Reinforcement (10-15s): Highlight key words.
    script_data = [
        {"word": "MINIMALISM", "start": 3.0, "end": 4.5},
        {"word": "IS POWER", "start": 4.5, "end": 6.0},
        {"word": "BOLD TYPE", "start": 6.0, "end": 8.0},
        {"word": "FAST MOTION", "start": 8.0, "end": 10.0},
        {"word": "ELEVATE", "start": 10.0, "end": 11.5},
        {"word": "YOUR", "start": 11.5, "end": 12.5},
        {"word": "CONTENT", "start": 12.5, "end": 15.0},
    ]

    captions = build_modern_captions(
        script_data,
        resolution,
        highlight_word="POWER",
        font=font_path,
        phrase_mode=True,
        y_pos=0.55,
    )

    # 6. Composite Main Segment
    main_video = CompositeVideoClip(
        [bg_clip, glow, noise, vignette, hook, flash, progress_bar] + captions,
        size=resolution,
        use_bgclip=True,
    )

    # 7. End Card (15-17.5s)
    end_card = create_end_card(
        resolution,
        duration=end_card_duration,
        text="SUBSCRIBE FOR TIPS",
        font=font_path,
    )

    # 8. Final Concatenation
    final_video = concatenate_videoclips(
        [main_video, end_card], method="compose", padding=-0.3
    )
    final_video = final_video.set_audio(audio_clip)

    # 9. Export
    if not os.path.exists("out"):
        os.makedirs("out")

    final_video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=os.cpu_count() or 4,
        preset="ultrafast",  # Faster for development
    )

    print(f"Video generated successfully: {output_path}")


if __name__ == "__main__":
    generate()
