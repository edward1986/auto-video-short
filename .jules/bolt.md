# Bolt's Journal

## 2025-05-14 - Initial Codebase Audit
**Learning:** Found repeated file I/O when opening video and audio clips in `produce_short.py`. Each `editor.VideoFileClip(path)` call incurs overhead of opening the file and reading metadata.
**Action:** Always store clip objects in variables if their properties (like duration) need to be accessed before further processing.

## 2025-05-15 - MoviePy Hierarchy Flattening & I/O Streaming
**Learning:** MoviePy rendering speed is heavily impacted by the depth of `CompositeVideoClip` nesting. Each nested composite adds recursive frame processing overhead. Flattening the clip hierarchy into a single list of clips for the final composite significantly improves performance. Additionally, streaming file data in `requests` (passing `f` instead of `f.read()`) reduces memory footprint during API calls.
**Action:** Avoid intermediate `CompositeVideoClip` objects when building complex overlays; pass all individual clips directly to the top-level composite. Always stream large file uploads.
