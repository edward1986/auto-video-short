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
    output_path = "final_2026_short.mp4"

    # 1. Background and Audio Setup
    bg_clip = editor.VideoFileClip(bg_path, audio=False, target_resolution=(1920, None)).resize(resolution)
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
    bg_clip = darken_clip(bg_clip, factor=0.45)
    # Dynamic cuts
    bg_clip = apply_dynamic_cuts(bg_clip, segment_duration=2.5)

    # 3. Overlays
    noise = create_noise_overlay(resolution, main_duration, opacity=0.12)
    glow = create_gradient_glow(resolution, main_duration, color=[(0, 255, 0), (255, 255, 255)], opacity=0.15)
    vignette = create_vignette(resolution, main_duration, opacity=0.5)
    progress_bar = create_progress_bar(resolution, main_duration, color=(0, 255, 0))
    flash = create_flash_transition(resolution).set_start(2.0)

    # 4. Content - Hook, Captions
    hook = create_hook_clip("THE FUTURE IS HERE", video_size=resolution, duration=2.0, font=font_path)

    # Script for captions
    # Core Message (3-10s)
    # Reinforcement (10-15s)
    script_data = [
        {"word": "2026", "start": 3.0, "end": 4.0},
        {"word": "DESIGN", "start": 4.0, "end": 5.0},
        {"word": "STYLE", "start": 5.0, "end": 6.0},
        {"word": "IS", "start": 6.0, "end": 6.5},
        {"word": "BOLD.", "start": 6.5, "end": 7.5},
        {"word": "MINIMAL.", "start": 7.5, "end": 8.5},
        {"word": "KINETIC.", "start": 8.5, "end": 10.0},

        {"word": "SCROLL-STOPPING", "start": 10.0, "end": 11.5},
        {"word": "VISUALS.", "start": 11.5, "end": 13.0},
        {"word": "PREMIUM", "start": 13.0, "end": 14.0},
        {"word": "MOTION.", "start": 14.0, "end": 15.0},
    ]

    captions = build_modern_captions(
        script_data,
        resolution,
        highlight_word="2026",
        font=font_path,
        phrase_mode=True,
        y_pos=0.55
    )

    # 5. Composite Main Segment
    main_video = CompositeVideoClip([
        bg_clip,
        glow,
        noise,
        vignette,
        hook,
        flash,
        progress_bar
    ] + captions, size=resolution, use_bgclip=True)

    # 6. End Card
    end_card = create_end_card(resolution, duration=end_card_duration, text="FOLLOW FOR MORE", font=font_path)

    # 7. Final Concatenation
    final_video = concatenate_videoclips([main_video, end_card], method="compose", padding=-0.3)
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
        preset="fast"  # Balanced for quality and speed
    )

    print(f"Video generated successfully: {output_path}")

if __name__ == "__main__":
    generate()
