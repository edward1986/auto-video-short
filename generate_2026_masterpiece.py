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
    print("🚀 Initiating 2026 Masterpiece Video Generation...")
    resolution = (1080, 1920)
    bg_path = "parkour.mp4"
    audio_path = "music.mp3"
    font_path = "default.ttf"
    output_path = "2026_masterpiece.mp4"

    # Robustness: Check if assets exist
    for path in [bg_path, audio_path, font_path]:
        if not os.path.exists(path):
            sys.exit(
                f"Error: Required asset '{path}' not found. Please ensure it exists in the root directory."
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
    # Ken Burns Zoom (1.0 to 1.2 for extra energy)
    bg_clip = apply_zoom(bg_clip, main_duration, start_scale=1.0, end_scale=1.2)
    # Darken for extreme contrast (0.35 factor)
    bg_clip = darken_clip(bg_clip, factor=0.35)
    # Fast dynamic cuts every 1.5s
    bg_clip = apply_dynamic_cuts(bg_clip, segment_duration=1.5)

    # 3. Overlays (Full 2026 Suite)
    noise = create_noise_overlay(resolution, main_duration, opacity=0.15)
    # Multi-color gradient glow (Electric Blue + Neon Green)
    glow = create_gradient_glow(
        resolution, main_duration, color=[(0, 255, 128), (0, 128, 255)], opacity=0.25
    )
    vignette = create_vignette(resolution, main_duration, opacity=0.7)
    progress_bar = create_progress_bar(resolution, main_duration, color=(0, 255, 128))
    # Sync flash with hook transition
    flash = create_flash_transition(resolution).set_start(2.0)

    # 4. Content - Hook (0-2s)
    hook = create_hook_clip(
        "2026 IS HERE", video_size=resolution, duration=2.0, font=font_path
    )

    # 5. Masterpiece Script
    # Optimized for fast scrolling: one idea at a time, bold emphasis.
    script_data = [
        {"word": "THE FUTURE", "start": 3.0, "end": 5.0},
        {"word": "OF CONTENT", "start": 5.0, "end": 7.0},
        {"word": "IS KINETIC", "start": 7.0, "end": 8.5},
        {"word": "MINIMAL", "start": 8.5, "end": 10.0},
        {"word": "AND BOLD", "start": 10.0, "end": 12.0},
        {"word": "MASTER THE", "start": 12.0, "end": 13.5},
        {"word": "NEW STANDARD", "start": 13.5, "end": 15.0},
    ]

    captions = build_modern_captions(
        script_data,
        resolution,
        highlight_word="KINETIC",
        font=font_path,
        phrase_mode=True,
        y_pos=0.55,  # Strict 2026 safe margin
    )

    # 6. Composite Main Segment
    main_video = CompositeVideoClip(
        [bg_clip, glow, noise, vignette, hook, flash, progress_bar] + captions,
        size=resolution,
        use_bgclip=True,
    )

    # 7. End Card (15-17.5s)
    end_card = create_end_card(
        resolution, duration=end_card_duration, text="SUBSCRIBE FOR MORE", font=font_path
    )

    # 8. Final Concatenation
    # Using small padding for smooth transition reset
    final_video = concatenate_videoclips(
        [main_video, end_card], method="compose", padding=-0.1
    )
    final_video = final_video.set_audio(audio_clip)

    # 9. Export
    if not os.path.exists("out"):
        os.makedirs("out")

    print(f"Exporting video to {output_path}...")
    final_video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=os.cpu_count() or 4,
        preset="fast",
    )

    print(f"✨ Masterpiece video generated successfully: {output_path}")


if __name__ == "__main__":
    generate()
