# Bolt's Journal

## 2025-05-14 - Initial Codebase Audit
**Learning:** Found repeated file I/O when opening video and audio clips in `produce_short.py`. Each `editor.VideoFileClip(path)` call incurs overhead of opening the file and reading metadata.
**Action:** Always store clip objects in variables if their properties (like duration) need to be accessed before further processing.

## 2025-05-15 - MoviePy Hierarchy Flattening & I/O Streaming
**Learning:** MoviePy rendering speed is heavily impacted by the depth of `CompositeVideoClip` nesting. Each nested composite adds recursive frame processing overhead. Flattening the clip hierarchy into a single list of clips for the final composite significantly improves performance. Additionally, streaming file data in `requests` (passing `f` instead of `f.read()`) reduces memory footprint during API calls.
**Action:** Avoid intermediate `CompositeVideoClip` objects when building complex overlays; pass all individual clips directly to the top-level composite. Always stream large file uploads.

## 2025-05-16 - MoviePy TextClip and Encoding Optimizations
**Learning:** Using `method='label'` instead of `method='caption'` for short strings (like countdown timers) significantly speeds up frame generation by bypassing complex layout engines. Additionally, setting `preset='fast'` and `threads=os.cpu_count()` in `write_videofile` provides a substantial boost to the final encoding phase.
**Action:** Prefer `method='label'` for simple text. Always utilize all available CPU cores and a fast encoding preset for rapid video iteration.

## 2025-05-17 - Redundant Processing and Regex Efficiency
**Learning:** Pre-compiled regex patterns avoids repeated compilation in helper functions. Furthermore, performing expensive operations (like base64 encoding of large video files) when their output is not needed (e.g., conditional email disabled) is a significant bottleneck that can be avoided with lazy evaluation or conditional blocks.
**Action:** Pre-compile regex at module level. Wrap expensive I/O and processing in conditional checks.

## 2025-05-18 - FFmpeg Offloading and Transformation Ordering
**Learning:** Using `target_resolution` in `VideoFileClip` offloads resizing to FFmpeg during decoding, which is significantly faster and more memory-efficient than resizing NumPy arrays in Python. Additionally, applying `.resize()` before `.loop()` ensures the transformation is only part of the base clip's graph, avoiding redundant processing on every loop iteration. In unformatted codebases, avoid broad reformatting to keep performance PRs focused and maintain git-blame history.
**Action:** Always use `target_resolution` for scaling during ingestion. Apply transformations as early as possible in the processing pipeline. Use surgical `# noqa` for pre-existing broken dependencies.

## 2025-05-19 - Efficient Gaussian Blur via Downscaling
**Learning:** Performing expensive image operations like Gaussian Blur on high-resolution assets (e.g., 1080x1920) is extremely CPU-intensive in Python. By downscaling the source image to 1/10th of its size before applying the blur and then upscaling the resulting clip back to the target resolution, we can achieve ~100x speedup with negligible visual impact for soft overlays like gradient glows.
**Action:** Always perform heavy filter/blur operations on a downscaled proxy before upscaling the final clip.

## 2025-05-20 - Scalar Math Performance in Temporal Lambdas
**Learning:** In MoviePy, temporal transformation functions (like `.resize(lambda t: ...)` or `.set_position(lambda t: ...)`) are called for every single frame. Using `numpy` for scalar math (e.g., `np.sin`, `np.exp`) inside these lambdas introduces significant overhead due to NumPy's internal array-handling machinery. Switching to the standard library `math` module for these scalar operations can result in a >70% speedup for the specific calculation, which compounds across thousands of frames.
**Action:** Always use the `math` module for scalar calculations inside MoviePy temporal callbacks.

## 2025-05-21 - MoviePy TextClip Caching and Lambda Closure Optimization
**Learning:** Creating `TextClip` objects in MoviePy is extremely expensive as it often triggers external ImageMagick calls and disk I/O for temporary files. By implementing a module-level cache for these clips based on their styling parameters, we can avoid redundant renders for repeated text elements (like captions or countdowns). Additionally, moving constant math (e.g., duration reciprocals or scale differences) out of temporal lambda functions into the parent closure provides a safe, measurable speedup for hot-path rendering logic executed on every frame.
**Action:** Always use a caching helper for repetitive `TextClip` creation. Pre-calculate all frame-independent constants before defining MoviePy temporal transformation functions.

## 2025-05-22 - LUT Optimization for Point-wise Image Operations
**Learning:** Point-wise operations (like darkening or brightness adjustment) on standard 8-bit images (`uint8`) are significantly faster when implemented via a Look-Up Table (LUT) rather than floating-point multiplication. A LUT replaces  \times W \times C$ multiplications with simple array indexing. However, this optimization is `dtype`-specific; it will fail on floating-point or 16-bit images. Always include a type check to ensure the optimization only applies to compatible data types, falling back to standard math for others to maintain robustness.
**Action:** Use cached LUTs for per-pixel intensity transformations on `uint8` image arrays. Always provide a safe fallback for non-`uint8` dtypes.

## 2025-05-23 - Safe Integer Upscaling and Hashable Cache Keys
**Learning:** When optimizing nearest-neighbor upscaling with `numpy.repeat`, dimensions must be exactly divisible by the scale factor to avoid shape mismatches (e.g., (1080, 1920) vs (1082, 1920) for 4x upscaling). Additionally, when using a dictionary as a cache for functions that accept a `size` argument (often passed as a list by libraries like MoviePy), always convert the input to a `tuple` to ensure it is hashable and avoid `TypeError`.
**Action:** Always check for divisibility before using `repeat` for upscaling, falling back to PIL for non-integer scales. Convert list-like inputs to tuples before using them as cache keys.

## 2025-05-24 - Avoid Lambda for Static Properties in MoviePy
**Learning:** In MoviePy 1.x, passing a lambda function (e.g., `lambda t: (0.5, 0.5)`) to methods like `set_position` or `resize` triggers a function call for every single frame during rendering. If the value is constant, passing the raw value (e.g., a tuple or float) allows MoviePy to skip these redundant calls.
**Action:** Always prefer static values over constant-returning lambdas for MoviePy clip properties to reduce per-frame overhead.

## 2025-05-25 - PIL-level Resizing and LUTs for Static Overlays
**Learning:** Resizing static overlays (like gradient glows or vignettes) at the MoviePy clip level causes redundant resizing operations for every frame during rendering. By resizing the source PIL image to the target resolution once during initialization, we eliminate this per-frame overhead. Furthermore, applying point-wise alpha channel adjustments using a Look-Up Table (LUT) is significantly faster than floating-point multiplication on large NumPy arrays, especially when the input range is limited to 8-bit integers (0-255).
**Action:** Always upscale static overlays once using PIL before creating MoviePy ImageClips. Use cached LUTs for per-pixel intensity or alpha transformations on uint8 arrays to avoid expensive arithmetic in initialization or temporal callbacks.
