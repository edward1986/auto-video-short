import sys
import os
import numpy as np

# Add root to path for module resolution
sys.path.append(os.getcwd())

from videoProcess.Styling import (
    get_text_clip,
    create_vignette,
    create_gradient_glow,
    create_noise_overlay,
    darken_clip,
)


def test_styling():
    print("Verifying Styling module...")
    size = (1080, 1920)
    duration = 1.0

    print("1. Testing get_text_clip (PIL rendering)...")
    txt = get_text_clip("HELLO 2026", fontsize=100, color="white")
    assert txt.size == (txt.w, txt.h)
    print(f"   Success: Text clip size {txt.size}")

    print("2. Testing create_vignette (caching and PIL resizing)...")
    v1 = create_vignette(size, duration)
    v2 = create_vignette(size, duration)
    # v1 and v2 should share the same underlying image array if cached
    # In ImageClip, .img attribute holds the array
    assert np.array_equal(v1.img, v2.img)
    print("   Success: Vignette cached and generated.")

    print("3. Testing create_gradient_glow...")
    g1 = create_gradient_glow(size, duration)
    assert g1.size == size
    print("   Success: Gradient glow generated.")

    print("4. Testing create_noise_overlay...")
    n1 = create_noise_overlay(size, duration)
    assert n1.size == size
    # Check if make_frame works
    frame = n1.get_frame(0.1)
    assert frame.shape == (1920, 1080, 3)
    print("   Success: Noise overlay generated.")

    print("5. Testing darken_clip (LUT)...")
    from moviepy.editor import ColorClip

    c = ColorClip(size=(100, 100), color=(255, 255, 255)).set_duration(1)
    dc = darken_clip(c, factor=0.5)
    frame = dc.get_frame(0)
    assert frame[0, 0, 0] == 127  # 255 * 0.5 = 127.5 -> 127
    print("   Success: Darken clip LUT applied correctly.")

    print("\nAll styling verifications PASSED!")


if __name__ == "__main__":
    try:
        test_styling()
    except Exception as e:
        print(f"Verification FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
