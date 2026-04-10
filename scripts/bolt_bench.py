import time
from moviepy.editor import ColorClip, CompositeVideoClip
from videoProcess.Styling import get_text_clip, build_modern_captions

def benchmark_composite_depth():
    print("--- Benchmarking CompositeVideoClip Overhead ---")
    size = (1080, 1920)
    duration = 5

    # 1. Baseline: Simple background
    bg = ColorClip(size=size, color=(0,0,0)).set_duration(duration)

    start = time.perf_counter()
    bg.get_frame(1.0)
    end = time.perf_counter()
    print(f"Single ColorClip frame: {end - start:.6f}s")

    # 2. Many individual clips (Simulating current captions)
    clips = [bg]
    for i in range(50):
        c = ColorClip(size=(100, 50), color=(255, 255, 255)).set_duration(duration).set_position((i*10, i*20))
        clips.append(c)

    comp = CompositeVideoClip(clips, size=size)
    start = time.perf_counter()
    comp.get_frame(1.0)
    end = time.perf_counter()
    print(f"Composite with 50 ColorClips frame: {end - start:.6f}s")

    # 3. Text rendering benchmark
    start = time.perf_counter()
    for _ in range(10):
        get_text_clip("BENCHMARK TEXT", fontsize=100)
    end = time.perf_counter()
    print(f"10x get_text_clip (cached): {end - start:.6f}s")

def benchmark_caption_generation():
    print("\n--- Benchmarking Caption Generation ---")
    words = [{"word": f"word{i}", "start": i*0.5, "end": (i+1)*0.5} for i in range(20)]
    video_size = (1080, 1920)

    start = time.perf_counter()
    clips = build_modern_captions(words, video_size)
    end = time.perf_counter()
    print(f"build_modern_captions (20 words) generated {len(clips)} clips in {end - start:.6f}s")

if __name__ == "__main__":
    benchmark_composite_depth()
    benchmark_caption_generation()
