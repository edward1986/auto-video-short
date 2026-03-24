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
