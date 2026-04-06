import time
from PIL import Image

if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS
from videoProcess.Styling import create_vignette, create_gradient_glow


def benchmark():
    size = (1080, 1920)
    duration = 10

    print("Benchmarking create_gradient_glow...")
    start = time.perf_counter()
    for _ in range(50):
        glow = create_gradient_glow(size, duration)
    end = time.perf_counter()
    print(f"Initialization (50 calls): {end - start:.4f}s")

    # Measure frame generation time
    start = time.perf_counter()
    for i in range(100):
        glow.get_frame(i / 10.0)
    end = time.perf_counter()
    print(f"Frame generation (100 frames): {end - start:.4f}s")

    print("\nBenchmarking create_vignette...")
    start = time.perf_counter()
    for _ in range(50):
        vignette = create_vignette(size, duration)
    end = time.perf_counter()
    print(f"Initialization (50 calls): {end - start:.4f}s")

    # Measure frame generation time
    start = time.perf_counter()
    for i in range(100):
        vignette.get_frame(i / 10.0)
    end = time.perf_counter()
    print(f"Frame generation (100 frames): {end - start:.4f}s")


if __name__ == "__main__":
    benchmark()
