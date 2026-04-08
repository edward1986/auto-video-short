import time
import os
import sys

# Ensure we can import from the current directory
sys.path.append(os.getcwd())

import numpy as np
from videoProcess.Styling import create_vignette, create_gradient_glow

def benchmark():
    size = (1080, 1920)
    duration = 10

    print("Benchmarking create_vignette...")
    start = time.perf_counter()
    for _ in range(20):
        create_vignette(size, duration)
    end = time.perf_counter()
    print(f"create_vignette (20 calls): {end - start:.4f}s")

    print("Benchmarking create_gradient_glow...")
    start = time.perf_counter()
    for _ in range(20):
        create_gradient_glow(size, duration)
    end = time.perf_counter()
    print(f"create_gradient_glow (20 calls): {end - start:.4f}s")

if __name__ == "__main__":
    benchmark()
