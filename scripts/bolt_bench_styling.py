import time
import math
import numpy as np
from moviepy.editor import ColorClip, CompositeVideoClip
from videoProcess.Styling import (
    apply_kinetic_motion,
    create_gradient_glow,
    create_progress_bar,
    get_text_clip
)

def verify_animation_fix():
    print("--- Verifying Animation Fix ---")
    resolution = (1080, 1920)
    clip = ColorClip((100, 100), color=(255, 0, 0)).set_duration(1)

    # Apply combined motion
    clip = apply_kinetic_motion(
        clip,
        slide_duration=0.4,
        direction="bottom",
        final_pos=("center", 0.7),
        float_amplitude=0.01
    )

    # Check pos at t=0 (should be slide offset + float offset)
    # Slide offset at t=0 is 1.0. Final pos is (0.5, 0.7).
    # Float offset at t=0: dx = 0.01 * sin(0) = 0, dy = 0.01 * cos(0) = 0.01
    # Expected: (0.5 + 0, 0.7 + 1.0 + 0.01) = (0.5, 1.71)
    pos0 = clip.pos(0)
    print(f"Pos at t=0: {pos0}")

    # Check pos at t=1.0 (slide is over, should be final pos + float offset)
    # Float at t=1.0: dx = 0.01 * sin(1.5), dy = 0.01 * cos(1.2)
    # Expected: (0.5 + 0.01*0.997, 0.7 + 0.01*0.362)
    pos1 = clip.pos(1.0)
    print(f"Pos at t=1.0: {pos1}")

    expected_x = 0.5 + 0.01 * math.sin(1.0 * 1.5)
    expected_y = 0.7 + 0.01 * math.cos(1.0 * 1.2)

    if abs(pos1[0] - expected_x) < 1e-5 and abs(pos1[1] - expected_y) < 1e-5:
        print("FIX VERIFIED: apply_kinetic_motion correctly combines slide and float.")
    else:
        print(f"Fix failed or logic mismatch. Expected ({expected_x}, {expected_y}), got {pos1}")

def bench_effects():
    print("\n--- Benchmarking Optimized Styling Effects ---")
    resolution = (1080, 1920)
    duration = 5.0

    # 1. Gradient Glow Mask Performance (Temporal Caching)
    print("Measuring Optimized Gradient Glow Mask (100 frames)...")
    glow = create_gradient_glow(resolution, duration)
    if glow.mask:
        # Warm up cache
        for t in np.linspace(0, duration, 100):
            _ = glow.mask.get_frame(t)

        start = time.perf_counter()
        for t in np.linspace(0, duration, 100):
            _ = glow.mask.get_frame(t)
        end = time.perf_counter()
        print(f"Glow mask get_frame (cached): {(end - start)/100:.6f}s per frame")
    else:
        print("No mask on glow.")

    # 2. Progress Bar Mask Performance (Pre-allocation)
    print("Measuring Optimized Progress Bar Mask (100 frames)...")
    pbar = create_progress_bar(resolution, duration)
    if pbar.mask:
        start = time.perf_counter()
        for t in np.linspace(0, duration, 100):
            _ = pbar.mask.get_frame(t)
        end = time.perf_counter()
        print(f"Progress Bar mask get_frame: {(end - start)/100:.6f}s per frame")
    else:
        print("No mask on pbar.")

    # 3. Composite Rendering Performance
    print("Measuring Composite Rendering (10 frames)...")
    cvc = CompositeVideoClip([glow, pbar], size=resolution)
    start = time.perf_counter()
    for t in np.linspace(0, 1, 10):
        _ = cvc.get_frame(t)
    end = time.perf_counter()
    print(f"Composite get_frame: {(end - start)/10:.6f}s per frame")

if __name__ == "__main__":
    try:
        verify_animation_fix()
        bench_effects()
    except Exception as e:
        print(f"Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
