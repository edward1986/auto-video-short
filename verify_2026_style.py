from moviepy.editor import ColorClip, CompositeVideoClip
from videoProcess.Styling import (
    create_noise_overlay,
    create_gradient_glow,
    create_vignette,
    create_hook_clip,
    build_modern_captions,
    create_end_card,
    darken_clip,
)


def verify_style():
    resolution = (1080, 1920)
    duration = 5.0

    # 1. Background
    bg = ColorClip(size=resolution, color=(50, 50, 50)).set_duration(duration)
    bg = darken_clip(bg, factor=0.45)

    # 2. Overlays
    noise = create_noise_overlay(resolution, duration, opacity=0.12)
    glow = create_gradient_glow(resolution, duration, color=(0, 255, 0), opacity=0.2)
    vignette = create_vignette(resolution, duration, opacity=0.5)

    # 3. Hook
    hook = create_hook_clip("VERIFY 2026", duration=2.0)

    # 4. Captions
    words = [
        {"word": "Bold", "start": 2.0, "end": 2.5},
        {"word": "Minimal", "start": 2.5, "end": 3.0},
        {"word": "Kinetic", "start": 3.0, "end": 4.0},
        {"word": "Typography", "start": 4.0, "end": 5.0},
    ]
    captions = build_modern_captions(
        words, resolution, highlight_word="Kinetic", phrase_mode=True
    )
    # Position captions at y=0.55
    captions = [c.set_position(("center", 0.55), relative=True) for c in captions]

    # 5. Composite
    video = CompositeVideoClip(
        [bg, glow, noise, vignette, hook] + captions, size=resolution
    )

    # 6. End Card
    end_card = create_end_card(resolution, duration=2.0)

    from moviepy.editor import concatenate_videoclips

    final = concatenate_videoclips([video, end_card], method="compose")

    output_path = "verify_2026_output.mp4"
    print(f"Rendering verification video to {output_path}...")
    # Render only 1 second of the first part and 1 second of the end card for speed
    final.subclip(0, 2).write_videofile(
        output_path, fps=12, codec="libx264", preset="ultrafast"
    )
    print("Verification video rendered successfully.")


if __name__ == "__main__":
    try:
        verify_style()
    except Exception as e:
        print(f"Style verification failed: {e}")
        import traceback

        traceback.print_exc()
