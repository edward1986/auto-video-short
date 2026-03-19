# Bolt's Journal

## 2025-05-14 - Initial Codebase Audit
**Learning:** Found repeated file I/O when opening video and audio clips in `produce_short.py`. Each `editor.VideoFileClip(path)` call incurs overhead of opening the file and reading metadata.
**Action:** Always store clip objects in variables if their properties (like duration) need to be accessed before further processing.

## 2025-05-15 - MoviePy Hierarchy Flattening & I/O Streaming
**Learning:** MoviePy rendering speed is heavily impacted by the depth of `CompositeVideoClip` nesting. Each nested composite adds recursive frame processing overhead. Flattening the clip hierarchy into a single list of clips for the final composite significantly improves performance. Additionally, streaming file data in `requests` (passing `f` instead of `f.read()`) reduces memory footprint during API calls.
**Action:** Avoid intermediate `CompositeVideoClip` objects when building complex overlays; pass all individual clips directly to the top-level composite. Always stream large file uploads.

## 2025-05-16 - Multi-threaded Encoding & FFmpeg Presets
**Learning:** Video encoding is the primary bottleneck in this pipeline. The original code used `min(os.cpu_count() or 4)`, which causes a `TypeError` because `min()` requires an iterable. Furthermore, using `preset='fast'` significantly reduces rendering time with negligible impact on quality for short-form content.
**Action:** Always enable multi-threading using `threads=os.cpu_count() or 4` (avoiding the `min()` bug) and use `preset='fast'` in `write_videofile` calls to optimize encoding speed.
