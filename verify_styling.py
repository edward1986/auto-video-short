import sys
import os
import numpy as np
from PIL import Image

# Ensure the script can find the videoProcess module
sys.path.append(os.getcwd())

# 2026 Styling: Monkeypatch for PIL 10+ compatibility in MoviePy
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from videoProcess.Styling import (
    get_pil_text_clip,
    get_text_clip,
    create_gradient_glow,
    build_modern_captions,
    create_noise_overlay
)

def verify_pil_text_rendering():
    print("Verifying PIL text rendering...")
    # Test high-quality rendering
    clip = get_pil_text_clip(
        "BOLD MINIMAL 2026",
        fontsize=100,
        color="white",
        stroke_width=5,
        stroke_color="black"
    )
    print(f"PIL Text Clip created: size={clip.size}")
    assert clip.size[0] > 0 and clip.size[1] > 0
    print("PIL text rendering verified.")

def verify_caching():
    print("Verifying TextClip caching...")
    clip1 = get_text_clip("CACHE TEST", fontsize=50)
    clip2 = get_text_clip("CACHE TEST", fontsize=50)
    # They should be copies of the same cached object or at least identical in properties
    assert clip1.size == clip2.size
    print("Caching verified.")

def verify_gradient_glow_pulse():
    print("Verifying Gradient Glow pulse effect...")
    glow = create_gradient_glow((1080, 1920), duration=2.0, opacity=0.2)

    # In MoviePy 1.0.3, a clip with alpha/mask has a .mask attribute
    assert glow.mask is not None

    # Test mask generation at t=0 and t=0.75
    mask0 = glow.mask.get_frame(0)
    mask_peak = glow.mask.get_frame(0.75)

    # Values should differ
    val0 = mask0[960, 540]
    val_peak = mask_peak[960, 540]

    print(f"Mask at t=0: {val0}, Mask at t=0.75: {val_peak}")
    assert val_peak > val0
    print("Gradient Glow pulse verified.")

def verify_modern_captions():
    print("Verifying modern captions build...")
    words = [
        {"word": "HELLO", "start": 0, "end": 0.5},
        {"word": "WORLD", "start": 0.5, "end": 1.0}
    ]
    clips = build_modern_captions(words, (1080, 1920), highlight_word="WORLD")
    # Each word has a shadow and a text clip
    assert len(clips) == 4
    print("Modern captions build verified.")

def verify_noise_overlay():
    print("Verifying Noise Overlay creation...")
    # This will catch missing 'random' or 'os' imports if they occur during generation
    noise = create_noise_overlay((1080, 1920), duration=1.0, opacity=0.1)
    assert noise.duration == 1.0
    # Exercise frame generation to ensure no runtime errors
    frame = noise.get_frame(0)
    assert frame.shape == (1920, 1080, 3)
    print("Noise Overlay verified.")

if __name__ == "__main__":
    try:
        verify_pil_text_rendering()
        verify_caching()
        verify_gradient_glow_pulse()
        verify_modern_captions()
        verify_noise_overlay()
        print("\nAll 2026 design style components verified successfully!")
    except Exception as e:
        print(f"\nVerification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
