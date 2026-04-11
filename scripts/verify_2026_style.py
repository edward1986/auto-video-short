import sys
import os
from PIL import Image

# Ensure project root is in path
sys.path.append(os.getcwd())

from videoProcess.Styling import get_text_clip


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

    # Test Left Alignment
    clip_l = get_text_clip(
        "LEFT ALIGN",
        fontsize=80,
        color="white",
        box_color=(0, 255, 0, 128),
        box_padding=20,
        align="left",
        size=(800, 200),
    )

    # Test Right Alignment
    clip_r = get_text_clip(
        "RIGHT ALIGN",
        fontsize=80,
        color="white",
        box_color=(0, 0, 255, 128),
        box_padding=20,
        align="right",
        size=(800, 200),
    )

    # Save frames
    if not os.path.exists("out"):
        os.makedirs("out")

    for name, clip in [("center", clip_c), ("left", clip_l), ("right", clip_r)]:
        frame = clip.get_frame(0)
        img = Image.fromarray(frame)
        path = f"out/verify_align_{name}.png"
        img.save(path)
        print(f"Saved {name} alignment to {path}")


if __name__ == "__main__":
    try:
        verify_style()
        print("Verification script finished successfully.")
    except Exception as e:
        print(f"Verification failed: {e}")
        sys.exit(1)
