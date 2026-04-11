import time
import numpy as np
import sys
import os
from moviepy.editor import ImageClip, ColorClip

# Ensure project root is in path
sys.path.append(os.getcwd())

from videoProcess.Styling import apply_zoom, darken_clip, get_pil_text_clip, apply_shake


def benchmark_apply_zoom():
    print("Benchmarking apply_zoom...")
    clip = ColorClip(size=(1080, 1920), color=(255, 0, 0), duration=10)
    zoomed = apply_zoom(clip, 10)

    start = time.perf_counter()
    for t in np.linspace(0, 10, 100):
        _ = zoomed.get_frame(t)
    end = time.perf_counter()
    print(f"apply_zoom (100 frames): {end - start:.4f}s")


def benchmark_darken_clip():
    print("Benchmarking darken_clip...")
    # Test with ImageClip (static)
    img_array = np.random.randint(0, 256, (1920, 1080, 3), dtype="uint8")
    clip = ImageClip(img_array).set_duration(10)
    darkened = darken_clip(clip, 0.45)

    start = time.perf_counter()
    for t in np.linspace(0, 10, 100):
        _ = darkened.get_frame(t)
    end = time.perf_counter()
    print(f"darken_clip on ImageClip (100 frames): {end - start:.4f}s")


def benchmark_get_pil_text_clip():
    print("Benchmarking get_pil_text_clip...")
    start = time.perf_counter()
    for _ in range(20):
        _ = get_pil_text_clip(
            "Hello World Optimization", fontsize=100, size=(1080, 200)
        )
    end = time.perf_counter()
    print(f"get_pil_text_clip (20 iterations): {end - start:.4f}s")


def benchmark_apply_shake():
    print("Benchmarking apply_shake...")
    clip = ColorClip(size=(100, 100), color=(255, 255, 255), duration=2).set_position(
        "center"
    )
    shaken = apply_shake(clip, duration=2)

    start = time.perf_counter()
    for t in np.linspace(0, 2, 100):
        # We need to get position at time t. In MoviePy, this is usually handled during composition.
        # But we can call the position function directly if we can access it.
        # shaken.pos(t) returns the position.
        _ = shaken.pos(t)
    end = time.perf_counter()
    print(f"apply_shake position (100 frames): {end - start:.4f}s")


if __name__ == "__main__":
    benchmark_apply_zoom()
    benchmark_darken_clip()
    benchmark_get_pil_text_clip()
    benchmark_apply_shake()
