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
    print("Starting 2026 Trend Video Generation...")
    resolution = (1080, 1920)
    bg_path = "parkour.mp4"
    audio_path = "music.mp3"
    font_path = "default.ttf"
    output_path = "2026_trend_video.mp4"

    # Robustness: Check if assets exist
    for path in [bg_path, audio_path, font_path]:
        if not os.path.exists(path):
            sys.exit(f"Error: Required asset '{path}' not found.")

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
    # Ken Burns Zoom
    bg_clip = apply_zoom(bg_clip, main_duration, start_scale=1.0, end_scale=1.2)
    # Darken for contrast
    bg_clip = darken_clip(bg_clip, factor=0.4)
    # Dynamic cuts every 2s
    bg_clip = apply_dynamic_cuts(bg_clip, segment_duration=2.0)

    # 3. Overlays
    noise = create_noise_overlay(resolution, main_duration, opacity=0.12)
    glow = create_gradient_glow(
        resolution, main_duration, color=[(0, 255, 128), (0, 128, 255)], opacity=0.2
    )
    vignette = create_vignette(resolution, main_duration, opacity=0.6)
    progress_bar = create_progress_bar(resolution, main_duration, color=(0, 255, 128))
    flash = create_flash_transition(resolution).set_start(2.0)

    # 4. Hook (0-2s)
    hook = create_hook_clip(
        "2026 DESIGN REVEALED", video_size=resolution, duration=2.0, font=font_path
    )

    # 5. Captions Script
    script_data = [
        {"word": "THE FUTURE", "start": 3.0, "end": 5.0},
        {"word": "IS MINIMAL", "start": 5.0, "end": 7.0},
        {"word": "BOLD", "start": 7.0, "end": 8.5},
        {"word": "AND KINETIC", "start": 8.5, "end": 10.5},
        {"word": "STAY AHEAD", "start": 10.5, "end": 13.0},
        {"word": "OF THE TREND", "start": 13.0, "end": 15.0},
    ]

    captions = build_modern_captions(
        script_data,
        resolution,
        highlight_word="FUTURE",
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
        resolution, duration=end_card_duration, text="FOLLOW THE TREND", font=font_path
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
        preset="fast",
    )

    print(f"Video generated successfully: {output_path}")

if __name__ == "__main__":
    generate()
