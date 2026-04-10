import numpy as np
from videoProcess.Styling import get_text_clip, darken_clip
from moviepy.editor import ImageClip

def test_styling_optimizations():
    print("Verifying styling optimizations...")

    # 1. Verify Shadow Rendering and Dimensions
    text = "SHADOW"
    sx, sy = (20, 20)
    # Ensure default box_padding (10) is consistent
    clip_no_shadow = get_text_clip(text, fontsize=100, box_padding=0)
    clip_with_shadow = get_text_clip(text, fontsize=100, shadow_color="black", shadow_offset=(sx, sy), box_padding=0)

    w1, h1 = clip_no_shadow.size
    w2, h2 = clip_with_shadow.size

    print(f"No shadow size: {w1}x{h1}")
    print(f"With shadow size: {w2}x{h2}")

    assert w2 >= w1 + sx, f"Width not increased enough for shadow. {w2} < {w1} + {sx}"
    assert h2 >= h1 + sy, f"Height not increased enough for shadow. {h2} < {h1} + {sy}"
    print("✅ Integrated shadow dimensions verified.")

    # 2. Verify Box Rendering and Padding
    pad = 50
    clip_no_box = get_text_clip(text, fontsize=100, box_padding=0)
    clip_with_box = get_text_clip(text, fontsize=100, box_color=(255, 0, 0, 255), box_padding=pad)

    wb1, hb1 = clip_no_box.size
    wb2, hb2 = clip_with_box.size

    print(f"No box size: {wb1}x{hb1}")
    print(f"With box size: {wb2}x{hb2}")

    # Padding is applied on all sides, so width should increase by 2*pad
    assert wb2 >= wb1 + 2*pad, f"Width not increased enough for padding. {wb2} < {wb1} + {2*pad}"
    print("✅ Integrated box padding verified.")

    # 3. Verify darken_clip static optimization (MoviePy 1.x)
    img_data = np.ones((100, 100, 3), dtype='uint8') * 100
    static_clip = ImageClip(img_data).set_duration(5).set_start(1)

    darkened = darken_clip(static_clip, factor=0.5)

    # In MoviePy 1.0.3, it should return a new ImageClip with .img
    assert hasattr(darkened, "img"), "Darkened clip missing .img attribute"
    assert darkened.img[0,0,0] == 50, f"Expected 50, got {darkened.img[0,0,0]}"
    assert darkened.duration == 5, f"Duration lost: {darkened.duration}"
    assert darkened.start == 1, f"Start lost: {darkened.start}"
    print("✅ darken_clip static optimization and property transfer verified.")

if __name__ == "__main__":
    try:
        test_styling_optimizations()
        print("ALL STYLE VERIFICATIONS PASSED")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"VERIFICATION FAILED: {e}")
        exit(1)
