import sys
import os
from PIL import Image

# Ensure project root is in path
sys.path.append(os.getcwd())

from videoProcess.Styling import get_text_clip, create_gradient_glow, create_hook_clip


def verify_style():
    print("Testing 2026 Integrated Styling...")

    # Test Center Alignment
    clip_c = get_text_clip(
        "CENTER ALIGN",
        fontsize=80,
        color="white",
        box_color=(255, 0, 0, 128),
        box_padding=20,
        align="center",
        size=(800, 200),
    )

    # Test Auto-scaling
    print("Testing auto-scaling with very long text...")
    clip_scale = get_text_clip(
        "THIS IS A VERY LONG PIECE OF TEXT THAT SHOULD AUTOMATICALLY SCALE DOWN TO FIT THE TARGET WIDTH WITHOUT OVERFLOWING",
        fontsize=150,
        color="white",
        size=(1000, None),
    )
    print(f"Auto-scaled clip size: {clip_scale.size}")

    # Test Gradient Glow with multiple colors
    print("Testing multi-color gradient glow...")
    glow = create_gradient_glow(
        (1080, 1920), 2.0, color=[(255, 0, 0), (0, 255, 0), (0, 0, 255)], opacity=0.3
    )

    # Test Hook Clip with size constraint
    print("Testing hook clip size constraint...")
    hook = create_hook_clip(
        "IMPACTFUL HOOK TEXT", video_size=(1080, 1920), fontsize=300
    )
    print(f"Hook clip size: {hook.size}")

    # Save frames
    if not os.path.exists("out"):
        os.makedirs("out")

    clips_to_verify = [
        ("center", clip_c),
        ("autosize", clip_scale),
        ("glow", glow),
        ("hook", hook),
    ]

    for name, clip in clips_to_verify:
        frame = clip.get_frame(0)
        img = Image.fromarray(frame)
        path = f"out/verify_2026_{name}.png"
        img.save(path)
        print(f"Saved {name} verify frame to {path}")


if __name__ == "__main__":
    try:
        verify_style()
        print("Verification script finished successfully.")
    except Exception as e:
        print(f"Verification failed: {e}")
        sys.exit(1)
